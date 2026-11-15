"""
웹캠으로 실시간 crack/corrosion 세그멘테이션 데모 (로컬 GTX 1060 등).

Jetson Orin 실추론 전에, "학습된 모델이 실물(테스트 철판·주변 사물)에 대해
그럴듯하게 반응하는가"를 눈으로 빠르게 확인하는 용도. Orin의 RTSP/TensorRT
파이프라인과는 별개 — 여긴 웹캠 + PyTorch(.pt) 로 도는 로컬 전용 데모.

사용법:
    python local_test/webcam_demo.py --weights <best.pt 경로>
    python local_test/webcam_demo.py --weights best.pt --camera 1 --imgsz 480 --conf 0.35

조작:
    q         종료
    s         현재 프레임(오버레이 포함) 스크린샷 저장 (local_test/_webcam_shots/)
    [ / ]     conf 임계값 0.05씩 낮추기/올리기
"""
from __future__ import annotations

import argparse
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np

# 클래스별 오버레이 색 (BGR).
CLASS_COLORS = {
    0: (0, 0, 255),      # crack — 빨강
    1: (0, 140, 255),    # corrosion — 주황
}
CLASS_NAMES = {0: "crack", 1: "corrosion"}


def draw_overlay(frame, result, line_width: int = 2):
    """results[0].plot() 대신 직접 그리기 — 클래스별 색을 CLASS_COLORS 로 고정."""
    vis = frame.copy()
    if result.boxes is None or len(result.boxes) == 0:
        return vis

    polys = result.masks.xy if result.masks is not None else None
    overlay = vis.copy()
    for i, box in enumerate(result.boxes):
        cid = int(box.cls[0])
        color = CLASS_COLORS.get(cid, (0, 255, 0))
        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
        conf = float(box.conf[0])
        name = CLASS_NAMES.get(cid, str(cid))

        if polys is not None and i < len(polys) and len(polys[i]) >= 3:
            pts = polys[i].astype(np.int32)
            cv2.fillPoly(overlay, [pts], color)
            cv2.polylines(vis, [pts], True, color, line_width)
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, line_width)

        label = f"{name} {conf * 100:.0f}%"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(vis, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
        cv2.putText(vis, label, (x1 + 3, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (255, 255, 255), 2)

    return cv2.addWeighted(overlay, 0.35, vis, 0.65, 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True, type=Path)
    ap.add_argument("--camera", type=int, default=0, help="cv2.VideoCapture 인덱스")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--iou", type=float, default=0.45)
    ap.add_argument("--device", default="0", help="'0'=GPU, 'cpu'=CPU")
    ap.add_argument("--width", type=int, default=1280, help="캡처 해상도(가로)")
    ap.add_argument("--height", type=int, default=720)
    args = ap.parse_args()

    from ultralytics import YOLO

    print(f"[load] {args.weights}")
    model = YOLO(str(args.weights))

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)  # Windows: DSHOW가 대체로 더 빠름
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        print(f"ERROR: 카메라 {args.camera} 를 열 수 없습니다.")
        return 2

    shots_dir = Path(__file__).parent / "_webcam_shots"
    shots_dir.mkdir(exist_ok=True)

    conf = args.conf
    fps_hist: deque[float] = deque(maxlen=30)
    win = "crack/corrosion live demo  (q:종료  s:저장  [ ]:conf조절)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    print("실시간 추론 시작. 창에 포커스 두고 q로 종료.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("프레임 읽기 실패 — 카메라 연결 확인.")
                break

            t0 = time.time()
            results = model.predict(
                frame, imgsz=args.imgsz, conf=conf, iou=args.iou,
                device=args.device, verbose=False,
            )
            dt = time.time() - t0
            fps_hist.append(1.0 / dt if dt > 0 else 0.0)
            fps = sum(fps_hist) / len(fps_hist)

            vis = draw_overlay(frame, results[0], line_width=2)  # 클래스별 색 고정(부식=마젠타)
            cv2.putText(vis, f"FPS {fps:4.1f}  conf {conf:.2f}  imgsz {args.imgsz}",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            cv2.imshow(win, vis)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                out = shots_dir / f"shot_{int(time.time())}.jpg"
                cv2.imwrite(str(out), vis)
                print(f"[saved] {out}")
            elif key == ord('['):
                conf = max(0.05, conf - 0.05)
            elif key == ord(']'):
                conf = min(0.95, conf + 0.05)
    finally:
        cap.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
