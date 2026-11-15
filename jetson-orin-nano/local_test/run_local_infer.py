"""
Colab 학습 결과(best.pt)를 로컬(GTX 1060 3GB)에서 검증한다.

  1) test split 에 대해 세그 지표 계산 (mask mAP50, mAP50-95, per-class)
  2) 샘플 이미지에 예측 오버레이 저장 (육안 확인)

사용법:
    python local_test/run_local_infer.py \
        --weights runs/cc_seg_v1/weights/best.pt \
        --data Dataset/crack_corrosion_seg/data.yaml \
        --n 24

메모:
    - 3GB VRAM 이므로 batch=1, imgsz=640 고정. OOM 나면 --device cpu.
    - best.pt 는 Drive 에서 내려받아 아무 경로에 두고 --weights 로 지정.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True, type=Path)
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default="0")
    ap.add_argument("--n", type=int, default=24, help="오버레이 저장할 샘플 수")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--split", default="test")
    args = ap.parse_args()

    from ultralytics import YOLO

    model = YOLO(str(args.weights))

    print(f"\n=== val on split='{args.split}' ===")
    metrics = model.val(
        data=str(args.data),
        split=args.split,
        imgsz=args.imgsz,
        batch=1,
        device=args.device,
        plots=True,
    )
    # seg 지표
    try:
        box = metrics.box
        seg = metrics.seg
        print(f"  BOX  mAP50={box.map50:.3f}  mAP50-95={box.map:.3f}")
        print(f"  MASK mAP50={seg.map50:.3f}  mAP50-95={seg.map:.3f}")
        for i, name in metrics.names.items():
            if i < len(seg.ap50):
                print(f"    - {name:10s}: mask AP50={seg.ap50[i]:.3f}")
    except Exception as e:  # noqa: BLE001
        print("  (지표 파싱 실패, metrics 원본 확인)", e)

    # 샘플 예측 오버레이
    data_dir = args.data.parent
    img_dir = data_dir / "images" / args.split
    imgs = [p for p in img_dir.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp")]
    random.seed(0)
    random.shuffle(imgs)
    imgs = imgs[: args.n]
    if imgs:
        print(f"\n=== predict {len(imgs)}장 -> runs/segment/predict* ===")
        model.predict(
            source=[str(p) for p in imgs],
            imgsz=args.imgsz,
            conf=args.conf,
            device=args.device,
            save=True,
            line_width=2,
        )
    print("\n완료. runs/segment/ 아래 결과 확인.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
