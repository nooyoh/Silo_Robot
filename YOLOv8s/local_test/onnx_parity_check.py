"""
best.pt (ultralytics) vs best.onnx (onnxruntime) 의 raw 출력이 일치하는지 확인.
Orin TensorRT 추론 코드가 파싱해야 할 텐서 형상/의미를 눈으로 확인하는 용도이기도 하다.

사용법:
    python local_test/onnx_parity_check.py \
        --pt  runs/cc_seg_v1/weights/best.pt \
        --onnx runs/cc_seg_v1/weights/best.onnx \
        --img  Dataset/crack_corrosion_seg/images/test/<something>.jpg

기대:
    - YOLOv8s-seg ONNX 출력 2개:
        output0: (1, 4+nc+32, 8400)   -> box(4) + class score(nc=2) + mask coef(32)
        output1: (1, 32, 160, 160)    -> mask prototype (imgsz=640 기준)
    - pt/onnx 의 output0 최대 절대오차 < 1e-3 이면 export 정상.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def letterbox(im, new=640, color=(114, 114, 114)):
    h, w = im.shape[:2]
    r = min(new / h, new / w)
    nh, nw = int(round(h * r)), int(round(w * r))
    im2 = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_LINEAR)
    top = (new - nh) // 2
    left = (new - nw) // 2
    out = np.full((new, new, 3), color, np.uint8)
    out[top:top + nh, left:left + nw] = im2
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", required=True, type=Path)
    ap.add_argument("--onnx", required=True, type=Path)
    ap.add_argument("--img", required=True, type=Path)
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()

    bgr = cv2.imread(str(args.img))
    if bgr is None:
        print(f"이미지 로드 실패: {args.img}")
        return 2
    lb = letterbox(bgr, args.imgsz)
    x = cv2.cvtColor(lb, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    x = np.transpose(x, (2, 0, 1))[None]  # NCHW

    # --- onnxruntime ---
    import onnxruntime as ort

    sess = ort.InferenceSession(str(args.onnx), providers=["CPUExecutionProvider"])
    outs = sess.run(None, {sess.get_inputs()[0].name: x})
    print("=== ONNX outputs ===")
    for o in sess.get_outputs():
        pass
    for i, arr in enumerate(outs):
        print(f"  output{i}: shape={arr.shape} dtype={arr.dtype} "
              f"min={arr.min():.4f} max={arr.max():.4f}")

    # --- ultralytics pt (raw) ---
    import torch
    from ultralytics import YOLO

    model = YOLO(str(args.pt))
    model.model.eval()
    with torch.no_grad():
        pt_out = model.model(torch.from_numpy(x))
    # pt_out: (preds, (proto, ...)) 형태 — 버전에 따라 다름
    def to_np(t):
        return t.detach().cpu().numpy() if hasattr(t, "detach") else np.asarray(t)

    preds = to_np(pt_out[0]) if isinstance(pt_out, (list, tuple)) else to_np(pt_out)
    print("\n=== PT raw output0 ===")
    print(f"  shape={preds.shape}")

    if preds.shape == outs[0].shape:
        diff = np.abs(preds - outs[0]).max()
        print(f"\noutput0 max abs diff (pt vs onnx): {diff:.6f}  "
              f"{'OK' if diff < 1e-3 else 'MISMATCH — export 확인 필요'}")
    else:
        print("\n[!] output0 형상 불일치 — 아래 형상 대조 후 Orin 파서 설계에 반영:")
        print(f"    pt  : {preds.shape}")
        print(f"    onnx: {outs[0].shape}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
