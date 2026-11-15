"""
Roboflow Universe에서 부식(corrosion) 인스턴스 세그멘테이션 데이터셋을 내려받는다.

사용법:
    # 1) 무료 Roboflow 계정 발급 후 API 키 확인 (https://app.roboflow.com > Settings > API)
    # 2) 환경변수로 키 전달
    ROBOFLOW_API_KEY=xxxxx python scripts/fetch_roboflow.py
    # 또는
    python scripts/fetch_roboflow.py --api-key xxxxx

내려받은 데이터는 Dataset/raw_downloads/<slug>/ 아래에 YOLOv8 세그 포맷으로 풀린다.
(data.yaml, train/ valid/ test/ 각각 images/ labels/)

주의:
- 여기 목록은 '후보'다. 내려받은 뒤 scripts/viz_labels.py 로 이미지를 눈으로 확인해
  근접 금속 표면 위주인지 검수하고, 아닌 것은 merge_and_split.py 의 SOURCES 에서 제외한다.
- Universe 데이터셋 대부분 CC BY 4.0. 채택分은 docs/dataset_licenses.md 에 기록한다.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# (workspace, project, version) — version=None 이면 최신 버전 자동 선택
CANDIDATES = [
    ("cawilai-interns-july-2023", "corrosion-instance-segmentation-sfcpc", None),
    ("corrosion-aom4m", "corrosion-sample", None),
    ("rust-detection", "rust-detection-38s6e", None),
    # 균열 보조 후보 (선택) — 필요 시 주석 해제
    # ("crack-dpq3s", "metal-crack-dcfng", None),
]

RAW_DIR = Path(__file__).resolve().parent.parent / "Dataset" / "raw_downloads"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-key", default=os.environ.get("ROBOFLOW_API_KEY"))
    ap.add_argument("--fmt", default="yolov8", help="export format (yolov8 = seg 포함)")
    args = ap.parse_args()

    if not args.api_key:
        print("ERROR: Roboflow API 키가 필요합니다. ROBOFLOW_API_KEY 환경변수 또는 --api-key 로 전달하세요.")
        return 2

    try:
        from roboflow import Roboflow
    except ImportError:
        print("roboflow 패키지가 없습니다.  pip install roboflow")
        return 2

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rf = Roboflow(api_key=args.api_key)

    ok, fail = [], []
    for ws, proj, ver in CANDIDATES:
        slug = f"{ws}__{proj}"
        dest = RAW_DIR / slug
        if dest.exists() and any(dest.iterdir()):
            print(f"[skip] 이미 존재: {dest}")
            ok.append(slug)
            continue
        try:
            project = rf.workspace(ws).project(proj)
            version = project.version(ver) if ver else project.versions()[0]
            print(f"[get ] {slug}  v{version.version}")
            version.download(args.fmt, location=str(dest))
            ok.append(slug)
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {slug}: {e}")
            fail.append(slug)

    print("\n=== 요약 ===")
    print("성공:", ok)
    print("실패:", fail)
    print(f"\n다음 단계: python scripts/viz_labels.py --root Dataset/raw_downloads/<slug> 로 육안 검수")
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
