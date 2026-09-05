from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path

from .pipeline import VisionPipeline, send_dry_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SiloRobot Orin vision pipeline (crack/corrosion seg)")
    parser.add_argument(
        "--model", type=Path,
        default=Path(os.getenv("SILOROBOT_MODEL", "artifacts/cc_seg_v1_fp16.engine")),
        help=".pt(로컬 테스트용) 또는 .engine(Orin 실배포, A안 — docs/orin_tensorrt_deploy.md 참고)",
    )
    parser.add_argument("--rtsp-url", default=os.getenv("SILOROBOT_RTSP_URL", "rtsp://100.121.144.38:8554/robot"))
    parser.add_argument("--websocket-url", default=os.getenv("SILOROBOT_WS_URL", "ws://100.74.141.112:8765"))
    parser.add_argument("--log-dir", type=Path, default=Path("logs"))
    parser.add_argument("--confidence", type=float, default=0.25, help="Colab 평가 임계값과 동일 기본값")
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--image-size", type=int, default=640, help="학습·export와 반드시 동일해야 함")
    parser.add_argument("--publish-fps", type=float, default=10.0)
    parser.add_argument("--mask-points", type=int, default=60, help="폴리곤 최대 점 수(대역폭 절약)")
    parser.add_argument("--dry-run", action="store_true", help="Send synthetic detections (with polygon) without RTSP/model")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.dry_run:
        asyncio.run(send_dry_run(args.websocket_url, args.log_dir))
        return
    pipeline = VisionPipeline(
        model_path=args.model,
        rtsp_url=args.rtsp_url,
        websocket_url=args.websocket_url,
        log_directory=args.log_dir,
        confidence=args.confidence,
        iou=args.iou,
        image_size=args.image_size,
        publish_fps=args.publish_fps,
        max_polygon_points=args.mask_points,
    )
    asyncio.run(pipeline.run())


if __name__ == "__main__":
    main()
