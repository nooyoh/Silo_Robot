"""
로컬 웹캠 → 대시보드 실시간 결함탐지 시연.

D:\\Silo_Robot\\YOLOv8s (기존 파일)는 전혀 수정하지 않고, 검증된
inference.messages / inference.pipeline.result_to_detections 를 그대로 import 해서 재사용한다.

구성 (한 프로세스):
  webcam(cv2, 이 프로세스가 유일하게 접근)
     ├─ HTTP MJPEG 서버(/stream.mjpg)  ──▶  대시보드(Qt, MediaPlayer.source 로 재생)
     └─ YOLO(best.pt) 추론 → polygon 포함 detection 메시지 ──WebSocket──▶ 대시보드(WS 서버, 8765)

ffmpeg 의 RTSP 서버 모드(-rtsp_flags listen)가 이 빌드 rtsp muxer 에 없어서(옵션 목록에 없음
확인됨) RTSP 대신 MJPEG-HTTP 로 대체 — 로컬 테스트 목적에는 충분하고 별도 서버 바이너리도 불필요.

사용법:
    python run_demo.py --model <best.pt 경로>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import queue
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import cv2

# 기존 YOLOv8s/inference 코드를 "사용"만 함 — 이 파일들은 수정하지 않는다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "YOLOv8s"))
from inference.messages import detection_message, hello_message  # noqa: E402
from inference.pipeline import result_to_detections  # noqa: E402

_latest_jpeg: bytes | None = None
_jpeg_lock = threading.Lock()

_latest_frame = None  # numpy ndarray, 추론 스레드가 읽어감
_frame_lock = threading.Lock()


class MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path != "/stream.mjpg":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        try:
            while True:
                with _jpeg_lock:
                    frame = _latest_jpeg
                if frame is None:
                    time.sleep(0.03)
                    continue
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                time.sleep(1 / 30)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, fmt, *args):  # 조용히
        pass


class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def capture_loop(args) -> None:
    """웹캠 전담. 최대한 빠르게(카메라 속도 그대로) 읽어서 영상 파일만 갱신 — 추론과 속도 무관."""
    global _latest_jpeg, _latest_frame
    # CAP_DSHOW 는 이 웹캠(Logi C270)에서 요청값(30fps)과 무관하게 실측 ~7fps로 막힘
    # (원인 불명 — 조명 문제 아님, MJPG fourcc 지정도 무효). CAP_MSMF 로는 실측 ~29fps —
    # 실측으로 확인 후 교체.
    cap = cv2.VideoCapture(args.camera, cv2.CAP_MSMF)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 내부 버퍼 최소화 — 오래된 프레임이 쌓이지 않게
    if not cap.isOpened():
        print(f"ERROR: 카메라 {args.camera} 를 열 수 없습니다.")
        return

    print("[capture] 시작 — 웹캠은 이 프로세스가 전담합니다.")

    # QML 의 Image 는 file:// URL 에 붙인 캐시버스터(?t=)를 무시하고 첫 프레임에 고정되는
    # 문제가 있었다 — 그래서 파일명 자체가 매번 바뀌도록 두 파일을 번갈아 쓴다.
    # (QML MainIndustrial.qml 의 pingPongPath() 와 접미사가 반드시 일치해야 함: _a / _b)
    live_path_a = live_path_b = None
    ping = False
    if args.live_image_path is not None:
        live_path_a = args.live_image_path.with_name(
            args.live_image_path.stem + "_a" + args.live_image_path.suffix)
        live_path_b = args.live_image_path.with_name(
            args.live_image_path.stem + "_b" + args.live_image_path.suffix)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue

            with _frame_lock:
                _latest_frame = frame  # 추론 스레드가 알아서 최신 것만 가져감

            ok2, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok2:
                continue
            data = buf.tobytes()
            with _jpeg_lock:
                _latest_jpeg = data
            if live_path_a is not None:
                # ping-pong: 매 프레임 다른 파일에 씀 -> QML source 문자열이 항상 바뀜.
                # 임시파일에 쓰고 rename 으로 원자적 교체(반쯤 써진 파일을 읽는 것 방지).
                # Windows 는 대상 파일을 다른 프로세스(QML)가 읽고 있으면 rename 을
                # PermissionError(WinError 5)로 거부한다 — POSIX와 달리 열려있는 파일
                # 위로 rename이 항상 되는 게 아님. 실패해도 다음 프레임(다른 슬롯)에서
                # 다시 시도하면 되므로 죽지 않고 건너뛴다.
                target = live_path_b if ping else live_path_a
                ping = not ping
                tmp = target.with_suffix(".tmp")  # live_frame_a.tmp / _b.tmp — 슬롯별로 이미 구분됨
                try:
                    tmp.write_bytes(data)
                    tmp.replace(target)
                except OSError:
                    pass
    finally:
        cap.release()


def inference_loop(model, det_queue: "queue.Queue", args) -> None:
    """추론 전담. capture_loop 와 속도가 달라도 됨 — 항상 '가장 최근' 프레임만 가져다 씀."""
    print("[infer] 시작 — 영상 갱신 속도와 무관하게 별도로 돕니다.")
    last_seen = None
    while True:
        with _frame_lock:
            frame = _latest_frame
        if frame is None or frame is last_seen:
            time.sleep(0.005)
            continue
        last_seen = frame

        results = model.predict(
            frame, conf=args.confidence, iou=args.iou, imgsz=args.imgsz, verbose=False,
        )
        h, w = frame.shape[:2]
        detections = result_to_detections(results[0], w, h, max_polygon_points=args.mask_points)
        try:
            det_queue.put_nowait(detection_message(detections))
        except queue.Full:
            pass


async def ws_sender(det_queue: "queue.Queue", ws_url: str) -> None:
    import websockets

    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                print(f"[ws] 대시보드에 연결됨: {ws_url}")
                await ws.send(json.dumps(hello_message()))
                while True:
                    message = await asyncio.to_thread(det_queue.get)
                    await ws.send(json.dumps(message))
        except Exception as e:  # noqa: BLE001
            print(f"[ws] 연결 실패/끊김, 재시도: {e}")
            await asyncio.sleep(1.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--imgsz", type=int, default=640)
    # 0.25 는 Colab 정량평가 기준값 — 육안 시연에는 너무 낮아서 애매한 순간 오검출이
    # 깜빡인다. 이 로컬 데모 전용으로만 0.6 으로 올림 (inference/, Colab 설정엔 영향 없음).
    ap.add_argument("--confidence", type=float, default=0.6)
    ap.add_argument("--iou", type=float, default=0.45)
    ap.add_argument("--mask-points", type=int, default=60)
    ap.add_argument("--http-port", type=int, default=8090)
    ap.add_argument("--ws-url", default="ws://127.0.0.1:8765")
    ap.add_argument(
        "--live-image", type=Path, default=None, dest="live_image_path",
        help="저지연 미리보기용 JPG 스냅샷 경로. 지정하면 대시보드 --live-image 에 같은 경로를 준다 "
             "(HTTP MJPEG보다 훨씬 낮은 지연 — 녹화/시연용). 기본값: local_webcam_demo/live_frame.jpg",
    )
    args = ap.parse_args()
    if args.live_image_path is None:
        args.live_image_path = Path(__file__).resolve().parent / "live_frame.jpg"

    from ultralytics import YOLO

    print(f"[load] {args.model}")
    model = YOLO(str(args.model))

    det_queue: "queue.Queue" = queue.Queue(maxsize=4)

    http_server = ThreadingHTTPServer(("0.0.0.0", args.http_port), MJPEGHandler)
    threading.Thread(target=http_server.serve_forever, daemon=True).start()
    print(f"[http] MJPEG 스트림(고지연, 참고용): http://127.0.0.1:{args.http_port}/stream.mjpg")
    print(f"[live] 저지연 스냅샷: {args.live_image_path}")
    print(f"        대시보드는 --live-image \"{args.live_image_path}\" 로 실행하세요 (권장, 지연 거의 없음).")

    threading.Thread(target=capture_loop, args=(args,), daemon=True).start()
    threading.Thread(target=inference_loop, args=(model, det_queue, args), daemon=True).start()

    try:
        asyncio.run(ws_sender(det_queue, args.ws_url))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
