"""
사일로봇 강재손상 데이터 전처리 스크립트
- TIFF 원본 이미지를 리사이즈된 JPG로 변환
- AI Hub JSON 라벨(COCO 유사 포맷)을 YOLO txt 포맷으로 변환
- Training/Validation 폴더 구조를 그대로 train/val로 매핑
- data.yaml 자동 생성

사용법 (WSL 터미널에서):
    python3 preprocess_steel_damage.py

실행 전에 아래 BASE_DIR, TRAIN_DIRS, VAL_DIRS 경로를 실제 다운로드 경로에 맞게 확인하세요.
"""

import json
import os
from pathlib import Path
from PIL import Image
from tqdm import tqdm

# ===================== 설정값 (필요시 수정) =====================

# aihubshell로 받은 데이터셋 최상위 경로
BASE_DIR = Path("/mnt/d/Silo_Robot/YOLOv8s/Dataset/112.건물_균열_탐지드론_개발을_위한_이미지/01.데이터")

# Training 쪽 원천데이터/라벨링데이터 폴더 (강재_강재손상만 사용)
TRAIN_IMAGE_DIR = BASE_DIR / "1.Training" / "원천데이터"
TRAIN_LABEL_DIR = BASE_DIR / "1.Training" / "라벨링데이터_240326_add"

# Validation 쪽
VAL_IMAGE_DIR = BASE_DIR / "2.Validation" / "원천데이터"
VAL_LABEL_DIR = BASE_DIR / "2.Validation" / "라벨링데이터_240326_add"

# 강재손상만 걸러내기 위한 필터
# - 실제 확인 결과: 압축 해제된 json/tiff 파일 경로에는 "강재손상"이라는 문자열이 없음
#   (예: 라벨링데이터_240326_add/201_uuid.json, 원천데이터/201_uuid.tiff 로 바로 풀림)
# - 다른 결함유형(도장손상, 콘크리트균열 등) zip은 애초에 받지 않았으므로,
#   폴더 안에는 강재손상 데이터만 존재함 -> 경로 필터는 불필요 (None으로 비활성화)
# - 대신 annotations[].attributes.class == "SteelDefect" 로 결함 종류를 재확인(안전장치)
FOLDER_KEYWORD = None         # 경로 필터 비활성화 (다른 결함유형 미다운로드 상태이므로 안전)
TARGET_CLASS = "SteelDefect"  # annotations[].attributes.class 매칭값 (실제 json 확인 결과)

# 출력 경로
OUTPUT_DIR = Path("/mnt/d/Silo_Robot/YOLOv8s/Dataset/steel_damage_dataset")

# 리사이즈 크기 (정사각형, 종횡비 무시하고 단순 리사이즈 - YOLO 정규화 좌표는 영향 없음)
IMG_SIZE = 640

# JPG 저장 품질
JPG_QUALITY = 90

# 클래스 정의 (강재손상 단일 클래스)
CLASS_NAMES = ["steel_damage"]

# ================================================================


def find_files(root: Path, exts, keyword=None):
    """
    root 아래에서 특정 확장자 파일들을 재귀적으로 찾음.
    keyword가 주어지면 '파일명' 또는 '경로 어딘가(폴더명 포함)'에 keyword가 포함된 것만 반환.
    (실제 데이터는 파일명이 아니라 상위 폴더명에 '강재손상'이 들어있는 구조)
    """
    result = []
    if not root.exists():
        return result
    for p in root.rglob("*"):
        if p.suffix.lower() in exts:
            if keyword is None or keyword in str(p):
                result.append(p)
    return result


def load_all_labels(label_dir: Path, folder_keyword: str):
    """
    라벨링데이터 폴더 아래의 모든 json을 읽어서
    file_name -> {"width":..,"height":..,"boxes":[[x,y,w,h], ...]} 형태로 통합
    - json이 이미지 1장당 1개 파일이든, 여러 이미지를 포함한 통합 파일이든 모두 처리
    - annotations[].attributes.class == TARGET_CLASS 인 것만 사용
    """
    lookup = {}
    json_files = find_files(label_dir, {".json"}, keyword=folder_keyword)

    for jf in tqdm(json_files, desc=f"라벨 json 파싱 ({label_dir.name})"):
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[경고] json 파싱 실패: {jf} ({e})")
            continue

        images = data.get("images", [])
        annotations = data.get("annotations", [])

        # image_id -> (file_name, width, height)
        img_meta = {}
        for im in images:
            img_meta[im["id"]] = (im["file_name"], im["width"], im["height"])

        for ann in annotations:
            # 결함 클래스 필터링: attributes.class가 TARGET_CLASS와 다르면 제외
            attrs = ann.get("attributes", {})
            ann_class = attrs.get("class")
            if TARGET_CLASS is not None and ann_class != TARGET_CLASS:
                continue

            img_id = ann.get("image_id")
            if img_id not in img_meta:
                continue
            file_name, width, height = img_meta[img_id]
            bbox = ann.get("bbox")
            if not bbox or len(bbox) != 4:
                continue

            key = Path(file_name).stem  # 확장자 제외한 파일명으로 매칭
            if key not in lookup:
                lookup[key] = {"width": width, "height": height, "boxes": []}
            lookup[key]["boxes"].append(bbox)

    return lookup


def bbox_to_yolo(bbox, img_w, img_h):
    """[x, y, w, h] 절대좌표 -> YOLO 정규화 [xc, yc, w, h] (0~1)"""
    x, y, w, h = bbox
    xc = (x + w / 2) / img_w
    yc = (y + h / 2) / img_h
    wn = w / img_w
    hn = h / img_h
    # 0~1 범위로 클램프 (좌표 오류 방지)
    xc = min(max(xc, 0.0), 1.0)
    yc = min(max(yc, 0.0), 1.0)
    wn = min(max(wn, 0.0), 1.0)
    hn = min(max(hn, 0.0), 1.0)
    return xc, yc, wn, hn


def process_split(image_dir: Path, label_dir: Path, split_name: str, folder_keyword: str):
    """Training 또는 Validation 하나를 처리해서 images/{split}, labels/{split}에 저장"""
    out_img_dir = OUTPUT_DIR / "images" / split_name
    out_lbl_dir = OUTPUT_DIR / "labels" / split_name
    out_img_dir.mkdir(parents=True, exist_ok=True)
    out_lbl_dir.mkdir(parents=True, exist_ok=True)

    label_lookup = load_all_labels(label_dir, folder_keyword)

    image_files = find_files(image_dir, {".tif", ".tiff"}, keyword=folder_keyword)
    print(f"[{split_name}] 대상 이미지 {len(image_files)}장 발견")

    matched = 0
    unmatched = 0

    for img_path in tqdm(image_files, desc=f"이미지 변환 ({split_name})"):
        key = img_path.stem
        if key not in label_lookup:
            unmatched += 1
            continue

        meta = label_lookup[key]
        img_w, img_h = meta["width"], meta["height"]

        # 이미지 리사이즈 + JPG 저장
        try:
            with Image.open(img_path) as im:
                im = im.convert("RGB")
                im_resized = im.resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
                out_img_path = out_img_dir / f"{key}.jpg"
                im_resized.save(out_img_path, "JPEG", quality=JPG_QUALITY)
        except Exception as e:
            print(f"[경고] 이미지 처리 실패: {img_path} ({e})")
            continue

        # YOLO 라벨 txt 저장 (정규화 좌표는 리사이즈와 무관하게 원본 크기 기준으로 계산)
        lines = []
        for bbox in meta["boxes"]:
            xc, yc, wn, hn = bbox_to_yolo(bbox, img_w, img_h)
            lines.append(f"0 {xc:.6f} {yc:.6f} {wn:.6f} {hn:.6f}")

        out_lbl_path = out_lbl_dir / f"{key}.txt"
        with open(out_lbl_path, "w") as f:
            f.write("\n".join(lines))

        matched += 1

    print(f"[{split_name}] 완료: 매칭 {matched}장, 라벨 없음(제외) {unmatched}장")


def write_data_yaml():
    yaml_path = OUTPUT_DIR / "data.yaml"
    names_block = "\n".join([f"  {i}: {name}" for i, name in enumerate(CLASS_NAMES)])
    content = f"""path: {OUTPUT_DIR}
train: images/train
val: images/val
names:
{names_block}
"""
    with open(yaml_path, "w") as f:
        f.write(content)
    print(f"data.yaml 생성 완료: {yaml_path}")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    process_split(TRAIN_IMAGE_DIR, TRAIN_LABEL_DIR, "train", FOLDER_KEYWORD)
    process_split(VAL_IMAGE_DIR, VAL_LABEL_DIR, "val", FOLDER_KEYWORD)

    write_data_yaml()
    print("\n전처리 완료. 결과물:", OUTPUT_DIR)


if __name__ == "__main__":
    main()