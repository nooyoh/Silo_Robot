from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

import cv2
import numpy as np
import websockets

from .logging_jsonl import JsonlDetectionLogger
from .messages import Detection, detection_message, hello_message

LOG = logging.getLogger(__name__)


def _simplify_polygon(points: np.ndarray, max_points: int) -> list[list[float]]:
    """WebSocket 페이로드 절약용 폴리곤 점 다운샘플. points: (N,2) 0~1 정규화."""
    if len(points) == 0:
        return []
    if len(points) > max_points:
        idx = np.linspace(0, len(points) - 1, max_points).astype(int)
        points = points[idx]
    return [[round(float(px), 4), round(float(py), 4)] for px, py in points]


def result_to_detections(result, frame_width: int, frame_height: int, max_polygon_points: int = 60) -> list[Detection]:
    """Ultralytics seg 모델의 Results 1개 -> Detection 목록.

    원본(단일클래스 crack detection)은 result.boxes 만 읽었다. 우리 모델은
    YOLOv8s-**seg**(cc_seg_v1, 0:crack/1:corrosion)라 result.masks 도 있고,
    Ultralytics가 이미 마스크를 폴리곤(result.masks.xyn, 정규화 완료)으로
    계산해서 준다 — 시그모이드/크롭/리사이즈를 직접 구현할 필요 없음
    (raw TensorRT로 갈 때만 필요, orin_reference/postprocess_seg.py 참고).
    """
    names = result.names
    detections: list[Detection] = []
    if result.boxes is None:
        return detections

    polygons_xyn = result.masks.xyn if result.masks is not None else None
    if polygons_xyn is None:
        LOG.warning("result.masks 가 없음 — seg 모델이 아니거나 export 설정을 확인할 것")

    for i, box in enumerate(result.boxes):
        x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
        class_id = int(box.cls[0])

        polygon: list[list[float]] = []
        if polygons_xyn is not None and i < len(polygons_xyn):
            polygon = _simplify_polygon(polygons_xyn[i], max_polygon_points)

        detections.append(
            Detection(
                x=x1 / frame_width,
                y=y1 / frame_height,
                width=(x2 - x1) / frame_width,
                height=(y2 - y1) / frame_height,
                label=str(names[class_id]),
                confidence=float(box.conf[0]),
                polygon=polygon,
            ).normalized()
        )
    return detections


class VisionPipeline:
    def __init__(
        self,
        model_path: Path,
        rtsp_url: str,
        websocket_url: str,
        log_directory: Path,
        confidence: float = 0.25,
        iou: float = 0.45,
        image_size: int = 640,
        publish_fps: float = 10.0,
        max_polygon_points: int = 60,
    ) -> None:
        from ultralytics import YOLO

        # model_path 가 .pt 든 .engine 이든 Ultralytics 가 알아서 로드한다
        # (엔진 변환은 A안 — docs/orin_tensorrt_deploy.md 참고. Orin 현지에서
        #  best.pt(or onnx) -> best.engine 을 미리 export 해서 여기 경로로 지정)
        self.model = YOLO(str(model_path))
        self.rtsp_url = rtsp_url
        self.websocket_url = websocket_url
        self.logger = JsonlDetectionLogger(log_directory)
        self.confidence = confidence
        self.iou = iou
        self.image_size = image_size
        self.publish_interval = 1.0 / publish_fps
        self.max_polygon_points = max_polygon_points

    async def run(self) -> None:
        reconnect_delay = 1.0
        while True:
            try:
                async with websockets.connect(
                    self.websocket_url, ping_interval=10, ping_timeout=10
                ) as websocket:
                    await websocket.send(json.dumps(hello_message()))
                    reconnect_delay = 1.0
                    await self._stream(websocket)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                LOG.warning("Pipeline disconnected: %s; retrying in %.1fs", error, reconnect_delay)
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2.0, 10.0)

    async def _stream(self, websocket) -> None:
        capture = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Unable to open RTSP stream: {self.rtsp_url}")

        frame_id = 0
        last_publish = 0.0
        warmed_up = False
        try:
            while True:
                ok, frame = await asyncio.to_thread(capture.read)
                if not ok:
                    raise RuntimeError("RTSP stream stopped producing frames")

                if not warmed_up:
                    # 엔진 로드 직후 첫 추론은 CUDA 커널 초기화로 느림 -> 결과 버리고 워밍업만
                    await asyncio.to_thread(
                        self.model.predict, frame, conf=self.confidence,
                        imgsz=self.image_size, verbose=False,
                    )
                    warmed_up = True
                    LOG.info("Warmup inference done")

                now = time.monotonic()
                if now - last_publish < self.publish_interval:
                    continue

                result = await asyncio.to_thread(
                    self.model.predict,
                    frame,
                    conf=self.confidence,
                    iou=self.iou,
                    imgsz=self.image_size,
                    verbose=False,
                )
                height, width = frame.shape[:2]
                detections = result_to_detections(result[0], width, height, self.max_polygon_points)
                message = detection_message(detections)
                await websocket.send(json.dumps(message, separators=(",", ":")))
                self.logger.write(frame_id, message)
                frame_id += 1
                last_publish = now
        finally:
            capture.release()


async def send_dry_run(websocket_url: str, log_directory: Path) -> None:
    """모델·RTSP 없이 통신 흐름만 확인. polygon 필드를 포함해서 보내므로
    Jetson/모델이 아직 없어도 대시보드(Qt)의 마스크 오버레이 렌더링을 먼저 테스트할 수 있다."""
    logger = JsonlDetectionLogger(log_directory)
    async with websockets.connect(websocket_url) as websocket:
        await websocket.send(json.dumps(hello_message()))
        message = detection_message([
            Detection(
                0.30, 0.25, 0.18, 0.35, "crack", 0.93,
                polygon=[[0.30, 0.25], [0.40, 0.27], [0.48, 0.40], [0.44, 0.60], [0.32, 0.55]],
            ),
            Detection(
                0.55, 0.50, 0.20, 0.15, "corrosion", 0.81,
                polygon=[[0.55, 0.50], [0.75, 0.52], [0.73, 0.65], [0.56, 0.63]],
            ),
        ])
        await websocket.send(json.dumps(message))
        logger.write(0, message)
