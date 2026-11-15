"""
Steelcrack 데이터셋(시맨틱 이진 마스크) → YOLOv8 세그멘테이션 폴리곤 라벨(class 0 = crack) 변환.

Steelcrack (He et al. 2024, Apache-2.0)
    https://github.com/hzlbbfrog/Civil-dataset
    512x512, train 3300 / val 525 / test 530, 이미지 + 이진 마스크 PNG.

준비:
    Google Drive/OneDrive 에서 zip 을 수동으로 받아 아래 위치에 푼다.
        Dataset/raw_downloads/steelcrack/
    내부 구조는 배포본에 따라 다를 수 있어 자동 탐색한다. 보통 아래 중 하나:
        steelcrack/{train,val,test}/{images,masks}/*.png
        steelcrack/{images,masks}/{train,val,test}/*.png
        steelcrack/{Train,Test}/... 등

사용법:
    python scripts/steelcrack_to_yolo_seg.py \
        --src Dataset/raw_downloads/steelcrack \
        --dst Dataset/raw_downloads/steelcrack_yolo

출력:
    <dst>/{train,val,test}/images/*.jpg
    <dst>/{train,val,test}/labels/*.txt   ("0 x1 y1 x2 y2 ..." 정규화 폴리곤, 균열마다 한 줄)
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import cv2
import numpy as np

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
CLASS_ID = 0  # crack

# 마스크에서 이 값(정규화 면적) 미만인 컨투어는 노이즈로 간주하고 버린다.
MIN_AREA_FRAC = 3e-5
# approxPolyDP epsilon = ARC_EPS * arclength (균열은 얇으므로 완만하게)
ARC_EPS = 0.0015
# 폴리곤 점 수 상한 (초과 시 균일 서브샘플)
MAX_POINTS = 120
# 얇은 균열이 선분으로 붕괴돼 폴리곤이 안 되는 것을 막기 위한 팽창(px). 0이면 비활성.
DILATE_PX = 2


def find_pairs(src: Path):
    """(split, image_path, mask_path) 목록을 최대한 유연하게 탐색."""
    masks: dict[str, Path] = {}
    images: dict[str, Path] = {}

    def split_of(p: Path) -> str:
        parts = [x.lower() for x in p.parts]
        for s, aliases in {
            "train": ("train", "training"),
            "val": ("val", "valid", "validation"),
            "test": ("test", "testing"),
        }.items():
            if any(a in parts for a in aliases):
                return s
        return "train"

    MASK_HINTS = ("mask", "label", "gt", "annotation", "/ann", "segmentation", "seg_")
    MASK_SUFFIXES = ("_mask", "-mask", "_gt", "-gt", "_label", "-label", "_seg", "-seg")

    def norm_stem(stem: str) -> str:
        s = stem.lower()
        for suf in MASK_SUFFIXES:
            if s.endswith(suf):
                return s[: -len(suf)]
        return s

    # Steelcrack 의 edges/ 등 이미지·마스크가 아닌 보조 폴더는 무시
    IGNORE_DIRS = ("edges", "edge", "boundary", "boundaries", "vis", "visualization", "overlay")

    for p in src.rglob("*"):
        if p.suffix.lower() not in IMG_EXTS or not p.is_file():
            continue
        parents = {x.lower() for x in p.parts[:-1]}
        if parents & set(IGNORE_DIRS):
            continue
        low = "/".join(x.lower() for x in p.parts)
        parent = p.parent.name.lower()
        is_mask = parent in ("masks", "mask", "labels", "gt", "annotations") or any(
            k in low for k in MASK_HINTS
        ) or any(p.stem.lower().endswith(suf) for suf in MASK_SUFFIXES)
        key = f"{split_of(p)}/{norm_stem(p.stem)}"
        (masks if is_mask else images)[key] = p

    pairs = []
    for key, mpath in masks.items():
        ipath = images.get(key)
        if ipath is None:
            stem = key.split("/", 1)[1]
            cand = [v for k, v in images.items() if k.split("/", 1)[1] == stem]
            ipath = cand[0] if cand else None
        if ipath is not None:
            pairs.append((key.split("/", 1)[0], ipath, mpath))
    return pairs


def mask_to_polygons(mask: np.ndarray) -> list[list[float]]:
    """이진 마스크 → 정규화 폴리곤 목록. 각 원소는 [x1,y1,x2,y2,...] (0~1)."""
    h, w = mask.shape[:2]
    bin_ = (mask > 127).astype(np.uint8)
    if bin_.sum() == 0:
        return []
    if DILATE_PX > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * DILATE_PX + 1, 2 * DILATE_PX + 1))
        bin_ = cv2.dilate(bin_, k)
    contours, _ = cv2.findContours(bin_, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polys: list[list[float]] = []
    for c in contours:
        area = cv2.contourArea(c)
        if area / float(h * w) < MIN_AREA_FRAC:
            continue
        eps = ARC_EPS * cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)
        if len(approx) < 3:
            # 얇은 균열이 선분으로 붕괴 → 원본 컨투어 점을 그대로(서브샘플) 사용
            approx = c.reshape(-1, 2)
            if len(approx) < 3:
                continue
        if len(approx) > MAX_POINTS:
            idx = np.linspace(0, len(approx) - 1, MAX_POINTS).astype(int)
            approx = approx[idx]
        norm = approx.astype(np.float64)
        norm[:, 0] = np.clip(norm[:, 0] / w, 0.0, 1.0)
        norm[:, 1] = np.clip(norm[:, 1] / h, 0.0, 1.0)
        polys.append(norm.reshape(-1).tolist())
    return polys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--dst", required=True, type=Path)
    ap.add_argument("--jpg-quality", type=int, default=92)
    args = ap.parse_args()

    if not args.src.exists():
        print(f"ERROR: 원본 경로가 없습니다: {args.src}")
        print("  Steelcrack zip 을 받아 이 위치에 풀어주세요 (README/plan 참고).")
        return 2

    pairs = find_pairs(args.src)
    if not pairs:
        print("ERROR: 이미지/마스크 쌍을 찾지 못했습니다. --src 내부 구조를 확인하세요.")
        print("  기대: mask/label/gt 등을 파일명·경로에 포함하는 PNG 가 마스크로 인식됩니다.")
        return 2

    counts: dict[str, int] = {}
    empty = 0
    for split, ipath, mpath in pairs:
        out_img = args.dst / split / "images"
        out_lbl = args.dst / split / "labels"
        out_img.mkdir(parents=True, exist_ok=True)
        out_lbl.mkdir(parents=True, exist_ok=True)

        mask = cv2.imread(str(mpath), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            continue
        polys = mask_to_polygons(mask)

        stem = f"sc_{ipath.stem}"
        img = cv2.imread(str(ipath), cv2.IMREAD_COLOR)
        if img is None:
            continue
        cv2.imwrite(str(out_img / f"{stem}.jpg"), img,
                    [cv2.IMWRITE_JPEG_QUALITY, args.jpg_quality])

        lines = [f"{CLASS_ID} " + " ".join(f"{v:.6f}" for v in poly) for poly in polys]
        (out_lbl / f"{stem}.txt").write_text("\n".join(lines))
        if not lines:
            empty += 1
        counts[split] = counts.get(split, 0) + 1

    print("=== 변환 완료 ===")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}장")
    print(f"  빈 라벨(마스크 비어있음): {empty}장  (음성 샘플로 유지)")
    print(f"  출력: {args.dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
