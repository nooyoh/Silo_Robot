"""
여러 YOLOv8-seg 소스 데이터셋을 하나의 2클래스(crack/corrosion) 데이터셋으로 병합·분할.

입력 소스는 아래 SOURCES 에 정의한다. 각 소스는:
  - kind="yolo": 이미 YOLOv8 세그 포맷 (images/ labels/ 가 split 폴더 아래 또는 위에 존재)
  - class_map: 원본 클래스 id -> 목표 클래스 id (None 이면 해당 인스턴스 제거)
  - prefix: 파일명 충돌 방지용

출력:
  Dataset/crack_corrosion_seg/
    images/{train,val,test}/  labels/{train,val,test}/  data.yaml

사용법:
  python scripts/merge_and_split.py                 # SOURCES 대로 병합
  python scripts/merge_and_split.py --copy          # 심볼릭 링크 대신 복사 (기본: 복사)
  python scripts/merge_and_split.py --val 0.1 --test 0.1 --seed 42

주의:
  - 소스별 원래 split 은 참고만 하고, 전체를 다시 셔플해 train/val/test 로 재분할한다
    (소스마다 split 정의가 제각각이라 통일이 안전). --respect-source-split 로 원본 유지 가능.
"""
from __future__ import annotations

import argparse
import hashlib
import random
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "Dataset" / "raw_downloads"
OUT = ROOT / "Dataset" / "crack_corrosion_seg"

NAMES = {0: "crack", 1: "corrosion"}
IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")

# ---- 병합 대상 정의 -------------------------------------------------------
# class_map : 원본 클래스 id -> 목표 id (원본 단일 클래스면 {0: <target>})
# max_images: 소스별 이미지 상한 (클래스 균형용, None=전체). 해시 기준 안정 샘플.
SOURCES = [
    {
        "name": "steelcrack",
        "path": RAW / "steelcrack_yolo",   # steelcrack_to_yolo_seg.py 출력
        "prefix": "sc",
        "class_map": {0: 0},               # crack
        "max_images": None,                # 약 4,355장 전부
    },
    {
        "name": "roboflow_corrosion_1",    # cawilai — CC BY 4.0, seg 폴리곤, nc=1 Corrosion
        "path": RAW / "cawilai-interns-july-2023__corrosion-instance-segmentation-sfcpc",
        "prefix": "rf1",
        "class_map": {0: 1},               # corrosion
        "max_images": None,                # 약 4,942장 전부 (crack 과 균형)
    },
    {
        "name": "roboflow_corrosion_2",    # corrosion-aom4m — CC BY 4.0, seg 폴리곤, nc=1
        "path": RAW / "corrosion-aom4m__corrosion-sample",
        "prefix": "rf2",
        "class_map": {0: 1},               # corrosion
        "max_images": 1500,                # 원본 ~32k → 과다, 1,500 으로 캡
    },
]
# ---------------------------------------------------------------------------


def find_label_files(src: Path):
    """소스 안의 모든 *.txt 라벨과 대응 이미지 경로를 찾는다.

    이미지는 라벨과 형제인 'labels' -> 'images' 디렉터리에서 같은 basename 으로 찾는다.
    (파일명에 점이 여러 개인 Roboflow 파일 `000001_jpg.rf.<hash>.txt` 대응 —
     Path.with_suffix 를 쓰면 `.<hash>` 를 확장자로 오인하므로 문자열로 처리.)
    거기서 못 찾을 때만 같은 디렉터리 트리를 한 번 인덱싱해 basename 으로 매칭.
    """
    labels = [p for p in src.rglob("*.txt")
              if p.parent.name == "labels" or "label" in p.parent.name.lower()]

    pairs = []
    misses = []
    for lp in labels:
        base = lp.name[:-4]  # ".txt" 제거, 나머지 basename 그대로
        img_dir = lp.parent.parent / "images"
        img = None
        for ext in IMG_EXTS:
            c = img_dir / f"{base}{ext}"
            if c.exists():
                img = c
                break
        if img is not None:
            pairs.append((img, lp))
        else:
            misses.append((lp, base))

    if misses:
        # 트리 전체를 한 번만 인덱싱 (basename -> path)
        index = {}
        for p in src.rglob("*"):
            if p.suffix.lower() in IMG_EXTS and p.is_file():
                index.setdefault(p.name, p)
                index.setdefault(p.stem, p)
        for lp, base in misses:
            img = index.get(base) or next(
                (index[k] for ext in IMG_EXTS if (k := f"{base}{ext}") in index), None)
            if img is not None:
                pairs.append((img, lp))
    return pairs


def remap_label(text: str, class_map: dict[int, int]) -> tuple[str, dict[int, int]]:
    """라벨 텍스트의 클래스 id 를 재매핑. (새 텍스트, 목표클래스별 인스턴스 수) 반환."""
    out_lines = []
    inst = defaultdict(int)
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 7:  # class + 최소 3점(6좌표)
            continue
        try:
            src_id = int(float(parts[0]))
        except ValueError:
            continue
        tgt = class_map.get(src_id)
        if tgt is None:
            continue
        coords = []
        for v in parts[1:]:
            try:
                f = float(v)
            except ValueError:
                coords = []
                break
            coords.append(min(max(f, 0.0), 1.0))
        if len(coords) < 6 or len(coords) % 2 != 0:
            continue
        out_lines.append(f"{tgt} " + " ".join(f"{c:.6f}" for c in coords))
        inst[tgt] += 1
    return "\n".join(out_lines), inst


def stable_split(key: str, val: float, test: float, seed: int) -> str:
    h = int(hashlib.md5(f"{seed}:{key}".encode()).hexdigest(), 16) % 10_000 / 10_000
    if h < test:
        return "test"
    if h < test + val:
        return "val"
    return "train"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--val", type=float, default=0.1)
    ap.add_argument("--test", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--link", action="store_true", help="복사 대신 하드링크 시도")
    ap.add_argument("--respect-source-split", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if OUT.exists() and not args.dry_run:
        print(f"[clean] 기존 {OUT} 삭제")
        shutil.rmtree(OUT)
    for sp in ("train", "val", "test"):
        (OUT / "images" / sp).mkdir(parents=True, exist_ok=True)
        (OUT / "labels" / sp).mkdir(parents=True, exist_ok=True)

    stats = defaultdict(lambda: defaultdict(int))   # stats[split]["img"/"crack"/"corrosion"]
    missing_sources = []
    total = 0

    for s in SOURCES:
        src: Path = s["path"]
        if not src.exists():
            missing_sources.append(s["name"])
            continue
        pairs = find_label_files(src)
        cap = s.get("max_images")
        if cap is not None and len(pairs) > cap:
            pairs.sort(key=lambda p: hashlib.md5(f"{args.seed}:{p[1].stem}".encode()).hexdigest())
            pairs = pairs[:cap]
            print(f"[{s['name']}] 라벨 {len(pairs)}개 (원본에서 {cap} 캡)  ({src})")
        else:
            print(f"[{s['name']}] 라벨 {len(pairs)}개 발견 ({src})")
        for img, lp in pairs:
            new_text, inst = remap_label(lp.read_text(errors="ignore"), s["class_map"])
            if not new_text:
                continue  # 목표 클래스 인스턴스 없음
            pfx = s["prefix"] + "_"
            stem = lp.stem if lp.stem.startswith(pfx) else pfx + lp.stem

            if args.respect_source_split:
                low = "/".join(x.lower() for x in lp.parts)
                split = ("val" if ("val" in low) else "test" if ("test" in low) else "train")
            else:
                split = stable_split(stem, args.val, args.test, args.seed)

            if args.dry_run:
                stats[split]["img"] += 1
                for k, v in inst.items():
                    stats[split][NAMES[k]] += v
                total += 1
                continue

            dst_img = OUT / "images" / split / f"{stem}{img.suffix.lower()}"
            dst_lbl = OUT / "labels" / split / f"{stem}.txt"
            if args.link:
                try:
                    dst_img.hardlink_to(img)
                except OSError:
                    shutil.copy2(img, dst_img)
            else:
                shutil.copy2(img, dst_img)
            dst_lbl.write_text(new_text)

            stats[split]["img"] += 1
            for k, v in inst.items():
                stats[split][NAMES[k]] += v
            total += 1

    if not args.dry_run:
        data_yaml = OUT / "data.yaml"
        data_yaml.write_text(
            f"path: {OUT.as_posix()}\n"
            "train: images/train\n"
            "val: images/val\n"
            "test: images/test\n"
            "names:\n"
            "  0: crack\n"
            "  1: corrosion\n"
        )

    print("\n=== 병합 결과 ===")
    for sp in ("train", "val", "test"):
        d = stats[sp]
        print(f"  {sp:5s}: images={d['img']:5d}  crack={d['crack']:5d}  corrosion={d['corrosion']:5d}")
    print(f"  총 이미지: {total}")
    if missing_sources:
        print(f"\n  [!] 없는 소스(건너뜀): {missing_sources}")
        print("      fetch_roboflow.py / steelcrack_to_yolo_seg.py 를 먼저 실행하거나")
        print("      SOURCES 의 path 를 실제 경로에 맞게 수정하세요.")
    if not args.dry_run:
        print(f"\n  data.yaml: {OUT / 'data.yaml'}")
        print("  다음: python scripts/viz_labels.py --root Dataset/crack_corrosion_seg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
