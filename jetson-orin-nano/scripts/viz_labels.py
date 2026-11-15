"""
YOLOv8-seg 폴리곤 라벨을 이미지 위에 그려 컨택트시트(JPG)로 저장 — 라벨 육안 검수용.

사용법:
    # 병합 데이터셋 검수
    python scripts/viz_labels.py --root Dataset/crack_corrosion_seg --n 25

    # Roboflow 원본 검수 (근접 금속 표면인지 확인)
    python scripts/viz_labels.py --root Dataset/raw_downloads/<slug> --n 25

옵션:
    --split train|val|test|all   (기본 all: 있으면 각각)
    --cls 0|1                    특정 클래스가 있는 이미지만
    --out <파일경로>             (기본: <root>/_viz_<split>.jpg)
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import cv2
import numpy as np

IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")
COLORS = {0: (0, 0, 255), 1: (0, 165, 255)}  # crack=red, corrosion=orange (BGR)
NAMES = {0: "crack", 1: "corrosion"}


def list_pairs(root: Path, split: str):
    lbl_dir = root / "labels" / split
    img_dir = root / "images" / split
    if not lbl_dir.exists():
        # split 폴더가 없는 레이아웃 (labels/*.txt 바로)
        lbl_dir = next((p for p in root.rglob("labels") if p.is_dir()), None)
        img_dir = next((p for p in root.rglob("images") if p.is_dir()), None)
        if lbl_dir is None:
            return []
    pairs = []
    for lp in sorted(lbl_dir.glob("*.txt")):
        for ext in IMG_EXTS:
            ip = img_dir / f"{lp.stem}{ext}"
            if ip.exists():
                pairs.append((ip, lp))
                break
    return pairs


def draw(ip: Path, lp: Path):
    img = cv2.imread(str(ip))
    if img is None:
        return None
    h, w = img.shape[:2]
    overlay = img.copy()
    for line in lp.read_text(errors="ignore").splitlines():
        p = line.split()
        if len(p) < 7:
            continue
        cid = int(float(p[0]))
        pts = np.array([float(x) for x in p[1:]], dtype=np.float32).reshape(-1, 2)
        pts[:, 0] *= w
        pts[:, 1] *= h
        pts = pts.astype(np.int32)
        col = COLORS.get(cid, (0, 255, 0))
        cv2.fillPoly(overlay, [pts], col)
        cv2.polylines(img, [pts], True, col, 2)
    img = cv2.addWeighted(overlay, 0.35, img, 0.65, 0)
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--split", default="all")
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--cls", type=int, choices=[0, 1])
    ap.add_argument("--cell", type=int, default=320)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    splits = ["train", "val", "test"] if args.split == "all" else [args.split]
    random.seed(args.seed)

    for split in splits:
        pairs = list_pairs(args.root, split)
        if args.cls is not None:
            pairs = [
                (i, l) for (i, l) in pairs
                if any(ln.startswith(f"{args.cls} ") for ln in l.read_text(errors="ignore").splitlines())
            ]
        if not pairs:
            print(f"[{split}] 없음")
            continue
        random.shuffle(pairs)
        pairs = pairs[: args.n]

        cols = int(np.ceil(np.sqrt(len(pairs))))
        rows = int(np.ceil(len(pairs) / cols))
        c = args.cell
        sheet = np.full((rows * c, cols * c, 3), 255, np.uint8)
        for i, (ip, lp) in enumerate(pairs):
            im = draw(ip, lp)
            if im is None:
                continue
            im = cv2.resize(im, (c, c))
            r, col = divmod(i, cols)
            sheet[r * c:(r + 1) * c, col * c:(col + 1) * c] = im

        out = args.out or (args.root / f"_viz_{split}.jpg")
        cv2.imwrite(str(out), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"[{split}] {len(pairs)}장 -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
