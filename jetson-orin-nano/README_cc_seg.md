# 사일로봇 결함탐지 v2 — crack / corrosion 세그멘테이션

`steeldamage_v1`(단일클래스, mAP50 0.115) 실패 후 재구현. 배경·진단은
`C:\Users\hylee\.claude\plans\lexical-twirling-sphinx.md` 참고.

- 클래스 2개: `0: crack`(균열), `1: corrosion`(부식)
- 라벨: 인스턴스 세그멘테이션(폴리곤)
- 도메인: 철제 표면 근접 이미지만
- 학습 Colab / 검증 로컬(GTX 1060) / 최종 추론 Jetson Orin Nano Super(TensorRT)

## 진행 순서

```bash
pip install -r scripts/requirements.txt

# 1) corrosion 데이터 (Roboflow Universe) — 무료 API 키 필요
ROBOFLOW_API_KEY=xxxx python scripts/fetch_roboflow.py
python scripts/viz_labels.py --root Dataset/raw_downloads/<slug>   # 근접 금속 표면인지 육안 검수

# 2) crack 데이터 (Steelcrack) — zip 수동 다운로드 후
#    https://github.com/hzlbbfrog/Civil-dataset  ->  Dataset/raw_downloads/steelcrack/
python scripts/steelcrack_to_yolo_seg.py --src Dataset/raw_downloads/steelcrack --dst Dataset/raw_downloads/steelcrack_yolo

# 3) 병합 + split + data.yaml
#    (scripts/merge_and_split.py 의 SOURCES 를 실제 채택 데이터셋에 맞게 수정)
python scripts/merge_and_split.py
python scripts/viz_labels.py --root Dataset/crack_corrosion_seg --n 25

# 4) zip 만들어 Drive 업로드
#    Dataset/crack_corrosion_seg -> crack_corrosion_seg.zip -> /MyDrive/YOLOv8s/

# 5) Colab 학습:  notebooks/silorobot_yolov8s_seg.ipynb

# 6) 로컬 검증 (best.pt, best.onnx 를 Drive 에서 받아서)
python local_test/run_local_infer.py  --weights <best.pt>  --data Dataset/crack_corrosion_seg/data.yaml
python local_test/onnx_parity_check.py --pt <best.pt> --onnx <best.onnx> --img <test 이미지>

# 7) Orin 배포:  inference/README.md
```

## 파일

| 경로 | 역할 |
|---|---|
| `scripts/fetch_roboflow.py` | Roboflow Universe 부식 세그 데이터셋 다운로드 |
| `scripts/steelcrack_to_yolo_seg.py` | Steelcrack 마스크 PNG → YOLO 폴리곤(class 0) |
| `scripts/merge_and_split.py` | 소스 병합·클래스 remap·train/val/test 분할·data.yaml |
| `scripts/viz_labels.py` | 폴리곤 오버레이 컨택트시트 (라벨 QA) |
| `notebooks/silorobot_yolov8s_seg.ipynb` | Colab 학습 + test 평가 + ONNX export |
| `local_test/run_local_infer.py` | 로컬 test split 지표 + 예측 오버레이 |
| `local_test/onnx_parity_check.py` | best.pt vs best.onnx 출력 대조 |
| `local_test/webcam_demo.py` | 웹캠 실시간 추론 데모 (로컬 PyTorch, 육안 확인용) |
| `docs/dataset_licenses.md` | 데이터셋 출처·라이선스 표 (보고서 부록) |
| `inference/` | 실제 `jetson-orin-nano/inference/` 이식용 사본. crack detection 전용 원본에 마스크 폴리곤(`result.masks.xyn`) 처리 추가. 로컬 dry-run e2e 검증 + 실제 best.pt로 result_to_detections() 검증 완료 |
| `inference/README.md` | Orin 보유자용 단독 실행 가이드 — 설치·엔진빌드(A안)·실행·트러블슈팅 |

## 상태 (2026-09-05 13:26)

- **Colab 학습 완료** (`cc_seg_v1`, 중간에 한 번 끊겼다가 `resume=True`로 재개해 100 epoch 완주): test split **Mask mAP50 0.580** (crack 0.755 / corrosion 0.405 — corrosion은 Roboflow 증강 잡음 영향, Phase B에서 개선 예정). v1(mAP50 0.115, det만)과 비교해 대폭 개선.
- `best.pt`/`best.onnx` 로컬 다운로드 완료(`runs/cc_seg_v1/weights/`). `local_test/run_local_infer.py`·`webcam_demo.py`로 로컬 검증 완료 — 실물 웹캠 실시간 데모까지 확인.
- **Orin 배포 코드 작성 완료**: 실제 `jetson-orin-nano/inference/`를 기반으로 2클래스 세그(마스크 폴리곤) 처리 추가한 사본을 `inference/`에 작성. 로컬에서 실제 `best.pt`로 `result_to_detections()` 검증(Ultralytics 자체 렌더링과 좌표 일치 확인) + dry-run e2e(WebSocket 통신) 검증 완료.
- **엔진 변환은 A안 채택** — Orin 위에서 `YOLO(...).export(format='engine', half=True)`. `trtexec`는 문제 생겼을 때만 진단용으로 사용(불필요 시 안 씀).
- **아직 Orin 실물이 없어 미검증**: RTSP 실수신, `.engine` 실빌드·실추론, 대시보드 연동. `inference/README.md`에 받았을 때 따라갈 순서를 정리해둠.
- `Dataset/112.*` 삭제(287GB 회수), `steel_damage_dataset/`는 zip만 유지.
- 상세 진행 이력: [docs/plan_cc_seg.md](docs/plan_cc_seg.md) "진행 현황"

## Phase B (9/8 이후)
로봇 카메라 실촬 데이터로 도메인 파인튜닝. 계획서 Phase B 절 참고.
