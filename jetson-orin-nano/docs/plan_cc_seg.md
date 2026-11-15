# 사일로봇 AI 결함탐지 재구현 계획 + 진행 현황 (crack / corrosion 세그멘테이션)

> 원본 계획서: `C:\Users\hylee\.claude\plans\lexical-twirling-sphinx.md` (2026-09-04 01:38 작성).
> 이 문서는 그 전문 + 실제 진행 현황·변경사항을 프로젝트 안에 보관하는 사본.

---

## ▓▓ 진행 현황 (2026-09-04 07:22 KST, 금요일 기준) ▓▓

### 완료

| 단계 | 상태 | 비고 |
|---|---|---|
| 원인 진단 (v1 실패) | ✅ | AI Hub 원본에 결함 세부유형 라벨 없음 확인 → 4클래스 불가. 라벨 일관성·도메인도 문제 |
| 디스크 정리 | ✅ | `Dataset/112.건물_균열_탐지드론` (287GB) 삭제, `steel_damage_dataset`는 zip만 유지. D: 여유 541GB |
| 파이프라인 스크립트·노트북·문서 작성 | ✅ | `scripts/`, `notebooks/`, `local_test/`, `docs/` |
| 로컬 스모크 테스트 | ✅ | 합성 데이터 e2e + 실데이터 1-epoch 세그 학습 (GTX1060) 무오류 |
| Steelcrack 다운로드·변환 | ✅ | Train 3300 / Validation 525 / Test 530, 마스크 PNG → YOLO 폴리곤 (빈 라벨 0) |
| Roboflow corrosion 다운로드 | ✅ | cawilai `corrosion-instance-segmentation-sfcpc` v16 (4,942장), corrosion-aom4m `corrosion-i0q5q` v11 (원본 ~32k, **1,500 캡**). 둘 다 CC BY 4.0 |
| 데이터 병합 (`crack_corrosion_seg/`) | ✅ | 총 10,267장 — train 8,506 / val 1,000 / test 761. 인스턴스: crack 11,153 / corrosion 71,722 |
| 라벨 QA (viz) | ✅ | crack 깨끗, corrosion 노이즈 有(증강본·이질 도메인·폴리곤 파편화) |
| 데이터셋 zip → Drive 업로드 | ✅ | `crack_corrosion_seg.zip` 718MB → `MyDrive/YOLOv8s/` |

### 진행 중

| 단계 | 상태 | 비고 |
|---|---|---|
| **Colab 학습** (`cc_seg_v1`) | 🟡 진행 중 | 07:22 기준 **epoch ~37/100**. Mask mAP50 ≈ **0.60**, Box mAP50 ≈ 0.61 (v1은 0.115). ~6분25초/epoch. **완료 예상: 3~7시간 후** (patience=20 조기종료 시 더 빠름). 결과는 Drive `silorobot_runs/cc_seg_v1/` 에 자동 저장 |

### 대기 (학습 완료 후)

1. Colab cell 5·6·7 수동 실행 (test 평가 / 예측 시각화 / ONNX export)
2. `best.pt`·`best.onnx`·`results.png`·`pred_test.zip` 로컬 다운로드
3. `python local_test/run_local_infer.py --weights best.pt --data Dataset/crack_corrosion_seg/data.yaml` — per-class 지표·오버레이 확인
4. `python local_test/onnx_parity_check.py` — ONNX 정합성
5. `docs/dataset_licenses.md` 인스턴스 수 최종 확정 (거의 반영됨)
6. (9/8 이후) Orin TensorRT 배포
7. (9/8 이후) Phase B: 로봇 실촬 데이터 도메인 파인튜닝

### 계획 대비 변경/실측

- **corrosion 인스턴스 폭증**(71,722): Roboflow 폴리곤이 녹 조각마다 분리돼 이미지당 평균 16개. 이미지 수 기준으론 crack:corrosion ≈ 50:50 이라 1차 학습 진행. per-class AP로 판단.
- **split 비율**: `--respect-source-split` 사용(소스 원래 split 존중) → 83/10/7. Steelcrack 공식 Test(530장)를 test에 그대로 보존(정직한 평가).
- **Steelcrack 실체**: 교량 강구조의 **도장(페인트)면 + 용접부** 근접샷. 맨철은 아님. "철제 구조물 표면"엔 부합, `dataset_licenses.md`에 명기.
- **rust-detection-38s6e 제외**: 바운딩박스 전용(세그 아님) + 잡클래스("car" 등).
- **학습 파라미터**: 계획대로 `epochs=100, imgsz=640, batch=-1, patience=20, close_mosaic=10, degrees=10, flipud=0.5, save_period=10, seed=42`. GPU_mem 5.13G 사용(batch AutoBatch ≈ 11~16).
- **스크립트 버그 3건 수정**: ① Steelcrack 이미지/마스크 짝 매칭(파일명 접미사) ② `merge_and_split` 이 점 여러 개인 Roboflow 파일명(`x_jpg.rf.<hash>.txt`)에서 `Path.with_suffix` 오작동 → 매 파일 전체 재탐색(3만장에서 사실상 정지) → 문자열 치환 방식으로 수정 ③ `sc_sc_` 이중 프리픽스.
- **노트북**: 로컬 파일(`notebooks/silorobot_yolov8s_seg.ipynb`)에 cell 8(런타임 자동 해제 `runtime.unassign()`) 추가함. **현재 Colab에서 돌고 있는 건 그 이전 버전**(9셀). 다음 학습부터 적용.

### resume (Colab 끊길 경우)

노트북에 정식 resume 셀은 없음. `save_period=10` + 매 epoch `last.pt`가 Drive에 저장되므로:
```python
from ultralytics import YOLO
YOLO(f'{RUN_PROJECT}/{RUN_NAME}/weights/last.pt').train(resume=True)
```
(cell 1~3 먼저 실행 → 위 셀. optimizer·LR 스케줄 유지, last.pt 시점부터 이어감)

---

## ▓▓ 진행 현황 업데이트 (2026-09-05 13:26 KST, 토요일) ▓▓

### 완료 (07:22 이후 추가분)

| 단계 | 상태 | 비고 |
|---|---|---|
| Colab 학습 재개·완주 | ✅ | 연결 끊김 발생(epoch 30대) → `YOLO(last.pt).train(resume=True)`로 epoch 81부터 재개 성공(처음부터 재시작 아님) → **100 epoch 완주** |
| test 평가 | ✅ | **Mask mAP50 0.580 / mAP50-95 0.303**. crack mask AP50 **0.755**, corrosion mask AP50 **0.405** — 클래스 간 격차 뚜렷(예상대로 corrosion 데이터 노이즈 영향) |
| 예측 시각화 검토 | ✅ | crack: 얇은 균열을 정확히 추적, 검사자 마커선과 실제 균열 구분함(다만 손글씨를 오검출한 사례 1건). corrosion: 실제 녹 텍스처는 정확하나 **Roboflow 색조 왜곡 증강 이미지에서 화면 전체를 corrosion으로 오검출**하는 경향 발견 — "색이 이상하면 corrosion"이라는 잘못된 지름길을 일부 학습한 것으로 추정 |
| `best.pt`/`best.onnx` 로컬 다운로드 | ✅ | `runs/cc_seg_v1/weights/` |
| 로컬 검증 | ✅ | `local_test/run_local_infer.py`(test 지표 재현) + `local_test/webcam_demo.py`(실시간 웹캠 데모, GTX1060에서 정상 동작) |
| Orin 배포 방식 결정 | ✅ | **A안 채택**: Orin에서 `YOLO(model_path)`가 `.pt`/`.engine` 그대로 로드 → Ultralytics가 전처리·NMS·마스크 디코딩 전담. raw TensorRT(B안, pycuda)는 검토만 하고 미채택 |
| 실제 `jetson-orin-nano/inference/` 코드 확보·리뷰 | ✅ | 사용자가 실제 레포 코드 업로드 → 이미 Ultralytics 기반(A안과 일치) 확인. 단 `result_to_detections()`가 `result.boxes`만 읽고 `result.masks`를 안 씀(세그 미지원) 발견 |
| `inference/` 작성 (Orin 이식용 사본) | ✅ | `messages.py`(Detection에 `polygon` 필드 추가), `pipeline.py`(`result.masks.xyn`로 마스크 폴리곤 추출 추가, 원본 재접속·publish-fps 로직 유지), `main.py`(--iou/--mask-points 옵션 추가, 기본 경로/신뢰도 갱신), `requirements.txt`, `README.md` |
| `inference/` 실동작 검증 | ✅ | ① 로컬 WebSocket 에코서버로 `--dry-run` e2e 확인(hello·polygon 포함 detection·JSONL 로깅) ② **실제 `best.pt`로 `result_to_detections()` 호출** → `res.names={0:'crack',1:'corrosion'}`, `res.masks is not None` 확인, 좌표 정규화 결과가 Ultralytics 자체 `result.plot()`과 시각적으로 일치 |
| Orin 배포 문서 전면 개편 | ✅ | "Orin 받으면 순서대로 따라가는 런북" 형태로 재작성(설치→엔진빌드→inference 실행→체크리스트), 이후 `inference/README.md`와 내용이 겹쳐 후자로 통합·정리. `trtexec`는 필수 아님(export가 TensorRT Python API 직접 호출) — 진단용 선택사항으로 재정리 |
| raw TensorRT 참고구현 작성·검토 | ✅ | pycuda 기반 엔진 래퍼·후처리·루프 골격을 참고용으로 작성했으나, A안(Ultralytics)만으로 충분해 불필요 판단 → 삭제 |

### 남은 것

1. **Orin 실물 입수 대기** — 받으면 `inference/README.md` 순서대로: JetPack 확인 → Python 환경(torch Jetson wheel) → `best.pt` 업로드 → `.engine` export(A안) → `--dry-run` → 실제 RTSP/실행
2. RTSP(Nano B01) → Orin 실수신, Orin ↔ 대시보드 WebSocket e2e — 전부 미검증(Orin 없어서)
3. 대시보드(Qt) 쪽에 `polygon` 필드 렌더링 코드 추가 필요(이 저장소 밖, 별도 확인)
4. (선택, 시간 되면) corrosion 오검출 완화 — 색조 왜곡된 Roboflow 증강 이미지를 학습셋에서 제외하고 재학습
5. (9/8 이후) Phase B: 로봇 카메라 실촬 데이터로 도메인 파인튜닝

### 정정된 사실

- Orin 배포 문서가 처음엔 raw TensorRT(B안) 위주로 상세했으나, 실제 `inference/` 코드를 확인한 결과 이미 Ultralytics 기반(A안)으로 짜여 있어 **B안은 불필요**한 것으로 정리됨. trtexec도 엔진 "빌드"에는 불필요(진단·벤치마크 때만 선택적으로 사용). 이후 별도 배포 문서는 `inference/README.md`로 통합.

---
---

## Context (원본 계획서)

기존 `steeldamage_v1` (YOLOv8s-det, `nc=1`, AI Hub `112.건물_균열_탐지드론`)은 mAP50 0.115로 실패.
직접 원본 라벨 JSON을 파싱해 확인한 결과:

- AI Hub 원본 annotation `attributes` = `{class, facility, lat, lon}` 뿐 → 결함 세부유형(crack/corrosion/…) 필드가 **원본에 존재하지 않음**. 인계 문서의 "4클래스 재라벨링"은 불가능.
- `class` 값도 `SteelDefect`(92%)에 `PaintDamage/Spalling/…`가 섞임. 리사이즈 640 이미지를 눈으로 확인하니 녹·박리 페인트·균열이 한 라벨에 뒤섞이고, 박스가 임의적이며 부분 어노테이션 다수.
- 이미지가 전부 **드론 항공/외벽 원거리 샷** → 로봇의 탱크·사일로 내벽 근접 화면과 도메인 불일치.
- 객체 크기·리사이즈·좌표 변환 자체는 정상 (박스 한 변 중앙값 98px @640) → 코드 버그 아님.

결론: 데이터/라벨 설계가 원인. 처음부터 다시 간다.

**목표**
- 클래스 2개: `0: crack`(균열), `1: corrosion`(부식). 라벨 형태 = **인스턴스 세그멘테이션**(폴리곤).
- 도메인: **철제 표면 근접 이미지만** 사용.
- ~9/8 한이음 마감: 공개 데이터셋(Roboflow + Steelcrack)으로 학습 → Colab 학습 → 로컬 테스트 → ONNX export → Orin TensorRT 배포 절차 문서화. 성능은 정직하게 병기.
- 9/8 이후: 로봇 카메라 실촬 데이터로 도메인 파인튜닝 (Phase B, 별도).

**실행 환경 사실**
- 로컬: Windows, `D:\Silo_Robot\YOLOv8s`, GTX 1060 3GB, Python 3.14, torch 2.11+cu126, ultralytics 8.4.56. → 로컬은 **추론/검증 전용**(학습 불가 수준 VRAM).
- 학습: Colab (T4).
- 최종 추론: Jetson Orin Nano Super (TensorRT). `orin-nano-super` 저장소는 로컬에 없음 → 코드 수정 불가, 배포는 **문서(스펙)로만** 정리.
- 라이선스: 공개 데이터셋(CC BY 4.0 / Apache-2.0) 사용 가능, 보고서에 출처·라이선스 표 명기.

---

## Phase A — 9/8까지 (공개 데이터 기반)

### A0. 폴더 구조 (신규, `D:\Silo_Robot\YOLOv8s` 아래)

```
Dataset/
  steel_damage_dataset/        # 기존 v1 — 건드리지 않음
  raw_downloads/               # 원본 다운로드 보관 (roboflow zip, steelcrack zip)
  crack_corrosion_seg/         # ★ 최종 병합 데이터셋
    images/{train,val,test}/
    labels/{train,val,test}/   # YOLO seg 폴리곤 txt (class 0=crack, 1=corrosion)
    data.yaml
scripts/
  fetch_roboflow.py            # Roboflow Universe 부식 seg 데이터셋 다운로드
  steelcrack_to_yolo_seg.py    # Steelcrack 시맨틱 마스크 PNG → YOLO 폴리곤 txt (class 0)
  merge_and_split.py           # 클래스 id 통일·중복 제거·train/val/test 분할·data.yaml 생성
  viz_labels.py                # 폴리곤 오버레이 컨택트시트 (라벨 QA)
notebooks/
  silorobot_yolov8s_seg.ipynb  # Colab: 학습 + val + ONNX export
local_test/
  run_local_infer.py           # test split에 대해 yolo segment val + predict (GTX1060)
  onnx_parity_check.py          # best.pt vs best.onnx 출력 일치 확인
docs/
  dataset_licenses.md          # 데이터셋 출처·라이선스·인용 표
preprocess_steel_damage.py     # 기존 — 유지
```

### A1. 데이터셋 확보

**corrosion (class 1) — Roboflow Universe, 이미 YOLOv8-seg 폴리곤 포맷**
- `scripts/fetch_roboflow.py`: `roboflow` pip 패키지 + 무료 API 키로 다운로드. `download("yolov8")`.
- 후보 (인스턴스 세그, 철제/금속 표면 근접 위주로 선별 — 실제 다운로드 후 이미지 육안 검수하여 채택):
  - `cawilai-interns-july-2023/corrosion-instance-segmentation-sfcpc` (~2k장)
  - `corrosion-aom4m/corrosion-sample` (~725장)
  - `rust-detection/rust-detection-38s6e`
  - 검수 기준: 근접 촬영 + 금속 표면. 자동차/원거리 위주 데이터셋은 제외.
- 목표: 검수 통과분에서 corrosion **~2,000–3,000장** 확보.

**crack (class 0) — Steelcrack (He et al. 2024, Apache-2.0)**
- 출처: https://github.com/hzlbbfrog/Civil-dataset (Google Drive/OneDrive 링크). 512×512, 시맨틱 이진 마스크, train 3,300 / val 525 / test 530.
- **다운로드는 사용자가 수동으로** zip 받아 `Dataset/raw_downloads/steelcrack/`에 배치 (gdown 차단 가능성).
- `scripts/steelcrack_to_yolo_seg.py`: 마스크 PNG → `cv2.findContours` → `approxPolyDP`로 단순화(점 수 상한 ~100) → 정규화 폴리곤 → `0 x1 y1 x2 y2 …` (균열 여러 개면 여러 줄). 면적 임계값 미만 컨투어 제거.
- crack 균형을 위해 corrosion 확보량에 맞춰 상한 샘플링 (예: 3,000장).

**crack 보조 (선택, 시간 남으면)**
- Roboflow `crack-dpq3s/metal-crack-dcfng` (metal crack 인스턴스 seg) 추가 검수 후 병합.

### A2. 병합·분할 — `scripts/merge_and_split.py`

- 각 소스의 라벨을 목표 클래스 id로 remap (Steelcrack→0, corrosion 소스들→1).
- 이미지 파일명 소스 프리픽스 부여(`sc_`, `rf1_`, …)로 충돌 방지.
- 손상 라벨/빈 라벨/이미지 없는 라벨 정리. 폴리곤 좌표 0–1 클램프.
- **소스별 원래 split을 존중**하되 최종 train/val/test ≈ 80/10/10 재구성. crack·corrosion이 각 split에 고루 들어가도록.
- `data.yaml` 생성: `path`, `train/val/test`, `names: {0: crack, 1: corrosion}`.
- 통계 출력: split×class 이미지·인스턴스 수, 폴리곤 점수 분포, 마스크 면적 분포.

### A3. 라벨 QA — `scripts/viz_labels.py`

- 각 split·클래스에서 무작위 N장에 폴리곤 오버레이 → 컨택트시트 JPG. 육안 검수 후 A2 파라미터(컨투어 임계값 등) 조정.

### A4. 로컬 스모크 테스트 (Colab 올리기 전, GTX1060)

- `yolo segment train model=yolov8s-seg.pt data=…/crack_corrosion_seg/data.yaml epochs=3 imgsz=512 batch=2 device=0` — 파이프라인·data.yaml·라벨 포맷이 도는지만 확인 (성능 아님).

### A5. Colab 학습 — `notebooks/silorobot_yolov8s_seg.ipynb`

기존 `silorobot_yolov8s.ipynb` 관례 유지: 학습은 `/content/`에서, Drive는 zip 보관·체크포인트 영속화용.

- 데이터셋 zip을 Drive `/content/drive/MyDrive/YOLOv8s/`에 두고 `/content/dataset`로 압축 해제.
- 학습:
  ```
  model = YOLO('yolov8s-seg.pt')
  model.train(
      data='/content/dataset/data.yaml',
      epochs=100, imgsz=640, batch=-1, patience=20,
      close_mosaic=10, degrees=10.0, flipud=0.5, fliplr=0.5, scale=0.5,
      save_period=10,
      project='/content/drive/MyDrive/YOLOv8s/silorobot_runs',
      name='cc_seg_v1')
  ```
- 학습 후: `model.val(split='test')` 지표 기록, `predict` 시각화 → Drive 복사.
- **ONNX export 셀 (신규)**:
  ```
  model.export(format='onnx', opset=17, imgsz=640, simplify=True)   # opset=17 프로젝트 표준
  ```
  seg 모델은 ONNX 출력 2개(detection + mask prototype) — Orin 추론 코드가 이를 처리해야 함(A7에 명시).
- best.pt / best.onnx / results.png / args.yaml을 Drive `silorobot_runs/cc_seg_v1/`에 영속화.

### A6. 로컬 검증 — `local_test/`

- `run_local_infer.py`:
  - `YOLO('best.pt').val(data=data.yaml, split='test')` → mask mAP50, mAP50-95, per-class 지표 출력.
  - test 이미지 일부에 `predict(save=True)` → 폴리곤/마스크 오버레이 저장, 육안 확인.
  - GTX1060 3GB: `imgsz=640, batch=1` 고정.
- `onnx_parity_check.py`: 동일 입력에 대해 `best.pt`(ultralytics) vs `best.onnx`(onnxruntime) raw 출력 비교 → export 정상 여부 확인. Orin 추론 코드 디버깅 기준선.

### A7. Orin 배포 문서 (스펙만, 코드 수정 없음)

- `best.onnx`(opset=17, imgsz=640, seg 2-output) → Orin에서:
  ```
  /usr/src/tensorrt/bin/trtexec --onnx=best.onnx --fp16 --saveEngine=cc_seg_v1_fp16.engine \
    --workspace=4096
  ```
- `orin-nano-super/inference/` 연동 시 확인 항목 체크리스트:
  - 입력 전처리: letterbox 640, RGB, /255, NCHW.
  - 출력 파싱: output0 = `[1, 4+2+32, 8400]` (box + 2 class + 32 mask coef), output1 = `[1, 32, 160, 160]` proto. 기존 단일클래스 det 파서와 **다름** — 클래스 2개 + 마스크 프로토 디코딩 추가 필요.
  - NMS + `sigmoid(coef @ proto)` → 마스크 리사이즈 → 임계값.
  - RTSP 수신 → 추론 → 결과(클래스·폴리곤·score) WebSocket 전송, Qt 오버레이.
- 실제 코드 반영은 `orin-nano-super` 저장소 접근 가능해지면 별도 작업.

### A8. 라이선스 표 — `docs/dataset_licenses.md`

- 채택한 각 데이터셋: 이름, URL, 라이선스(CC BY 4.0 / Apache-2.0 등), 인용(BibTeX), 이미지·인스턴스 수. 보고서 부록용.

---

## Phase B — 9/8 이후 (도메인 파인튜닝, 개요만)

- 로봇 IMX219 카메라 + LED로 테스트 철판/실제 구조물 근접 촬영 → 수백 장.
- Roboflow 또는 `labelme`로 crack/corrosion 폴리곤 라벨링.
- `cc_seg_v1/best.pt`에서 이어 파인튜닝 (낮은 lr, freeze backbone 일부, mosaic off).
- 도메인 test set으로 재평가 → Orin 재배포.
- 별도 계획 문서로 분리.

---

## 필요 사전 준비 (사용자)

1. **Roboflow 무료 계정 + API 키** (Universe 데이터셋 다운로드용).
2. **Steelcrack zip 수동 다운로드** → `D:\Silo_Robot\YOLOv8s\Dataset\raw_downloads\steelcrack\`.
3. Colab Pro (기존 보유), Google Drive `/MyDrive/YOLOv8s/`.

---

## Verification (end-to-end)

1. `scripts/fetch_roboflow.py` 실행 → `raw_downloads/`에 corrosion 데이터셋. 이미지 육안 검수(근접 금속 여부).
2. `scripts/steelcrack_to_yolo_seg.py` 실행 → crack 폴리곤 txt 생성. `viz_labels.py`로 오버레이 검수.
3. `scripts/merge_and_split.py` → `crack_corrosion_seg/` + `data.yaml` + 통계 출력. split×class 균형 확인.
4. A4 로컬 3-epoch 스모크 학습 무오류 통과.
5. Colab 100-epoch 학습 완료, `results.png` 수렴 확인, `val(split='test')` per-class mask mAP 기록.
6. `local_test/run_local_infer.py` → test split 지표 재현 + 오버레이 육안 확인.
7. `local_test/onnx_parity_check.py` → pt vs onnx 출력 max abs diff < 1e-3.
8. Orin 배포 문서, `docs/dataset_licenses.md` 작성 완료.

## 리스크 / 유의

- **crack ↔ corrosion 소스 분리**: 각 소스가 한 클래스만 포함 → 모델이 "이미지당 한 종류"로 편향될 수 있음. 두 결함이 함께 있는 이미지가 거의 없음을 감안, 지표는 per-class로 해석.
- **9/8 현실 목표**: mask mAP50 0.3~0.5 수준이면 "파이프라인 동작 + 공개데이터 학습" 근거로 충분. 도메인 전이 한계는 보고서에 명시하고 Phase B로 연결.
- Steelcrack은 교량 강구조 균열 → 탱크·사일로와 완전 일치는 아니지만 "철제 표면 근접"에는 부합.
- Python 3.14 로컬 환경: 일부 패키지 경고 가능. ultralytics 8.4.56은 설치·동작 확인됨.
