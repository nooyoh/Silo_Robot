# inference/ — Jetson Orin Nano Super 실행 가이드

crack/corrosion 세그멘테이션(YOLOv8s-seg, 2클래스) 모델을 Nano B01 RTSP 영상에 대해
실시간 추론하고, 결과를 대시보드에 WebSocket으로 전송하는 코드. 이 폴더를 그대로
`jetson-orin-nano` 레포의 `inference/`에 덮어써서 쓴다.

---

## 0. 받아야 할 것

- 이 `inference/` 폴더 전체
- `best.pt` (Colab 학습 산출물) — Orin으로 옮겨서 **Orin 현지에서** 엔진으로 변환한다 (다른 장비에서 만든 엔진 파일은 Orin에서 못 씀)
  - 로컬 경로: `runs/cc_seg_v1/weights/best.pt`
  - Google Drive 경로: **내 드라이브 › YOLOv8s › silorobot_runs › cc_seg_v1 › weights › best.pt**

---

## 1. 설치

### 1-1. JetPack 확인 (CUDA/cuDNN/TensorRT는 이미 시스템에 있음 — pip로 따로 설치 금지)

```bash
dpkg -l | grep -i tensorrt
python3 -c "import tensorrt as trt; print(trt.__version__)"
```

### 1-2. 가상환경

```bash
python3 -m venv --system-site-packages ~/venvs/orin-infer
source ~/venvs/orin-infer/bin/activate
```
`--system-site-packages`가 필수다 — 시스템 `tensorrt`(그리고 필요시 GStreamer 포함 `cv2`)를 venv 안에서도 보이게 하기 위함.

### 1-3. PyTorch — Jetson 전용 wheel을 **먼저** 수동 설치

```bash
# JetPack 버전에 맞는 wheel을 아래에서 확인 후 설치
#   https://developer.nvidia.com/embedded/downloads  또는  jetson-ai-lab(dusty-nv)
pip install torch-<ver>-cp<py>-cp<py>-linux_aarch64.whl
pip install torchvision-<ver>-cp<py>-cp<py>-linux_aarch64.whl

python3 -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# torch.cuda.is_available() 이 True 여야 한다 — False면 wheel이 잘못된 것
```

### 1-4. 나머지 설치

```bash
cd inference
pip install -r requirements.txt      # ultralytics, websockets, numpy, opencv-python

# torch가 안 바뀌었는지 재확인
python3 -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

각 패키지를 왜 넣었는지/왜 pip로 깔면 안 되는 게 있는지는 `requirements.txt` 안 주석 참고.

### 1-5. 설치 확인

```bash
python3 -c "import tensorrt, torch, cv2, websockets, ultralytics; \
print('OK: tensorrt', tensorrt.__version__, '| torch cuda', torch.cuda.is_available())"
```

### 1-6. 전력/클럭 고정 (실시간 추론 전 항상)

```bash
sudo nvpmodel -m 0     # MAXN
sudo jetson_clocks
```
안 하면 같은 모델인데도 측정할 때마다 지연시간이 들쭉날쭉하게 나온다.

---

## 2. 모델 업로드 + 엔진 빌드

```bash
mkdir -p artifacts
scp <로컬PC>:D:/Silo_Robot/YOLOv8s/runs/cc_seg_v1/weights/best.pt artifacts/best.pt
```

엔진 빌드는 **Orin 현지에서** 한 줄이면 끝난다 (TensorRT 엔진은 빌드한 GPU·TensorRT 버전에 종속돼 다른 장비에서 만든 걸 못 쓴다):

```bash
python3 -c "
from ultralytics import YOLO
m = YOLO('artifacts/best.pt')
m.export(format='engine', imgsz=640, half=True, device=0, workspace=4)
"
mv artifacts/best.engine artifacts/cc_seg_v1_fp16.engine
```
- `half=True`(FP16) — Orin Nano 처리량 핵심, 사실상 필수
- `imgsz=640` — 학습 때와 반드시 동일. 다르면 좌표가 어긋난다
- `workspace=4`(GiB) — 메모리 부족하면 2 등으로 낮추기
- **`trtexec`는 필요 없다** — `export()`가 TensorRT Python API를 직접 호출해서 엔진을 만든다. export가 애매한 에러로 실패할 때만 진단용으로 직접 돌려본다:
  ```bash
  sudo ln -s /usr/src/tensorrt/bin/trtexec /usr/local/bin/trtexec   # 보통 이 경로
  trtexec --onnx=artifacts/best.onnx --fp16 --saveEngine=/tmp/debug.engine --verbose
  ```
  `--verbose` 레이어별 로그로 어느 op에서 막히는지 확인.

---

## 3. 실행

### 3-1. dry-run — 모델·RTSP 없이 통신만 먼저 확인

```bash
python -m inference.main --dry-run --websocket-url ws://<대시보드-ip>:<port>
```
crack 1개 + corrosion 1개(둘 다 `polygon` 포함) 가짜 데이터를 보낸다. **모델·Jetson 카메라 연결 전에 대시보드(Qt) 쪽 마스크 오버레이 렌더링부터 검증**할 수 있다. (이 경로는 로컬 PC에서 이미 실동작 확인됨 — WS 연결·hello·polygon 메시지·JSONL 로깅 전부 정상.)

### 3-2. 실제 실행

```bash
python -m inference.main \
  --model artifacts/cc_seg_v1_fp16.engine \
  --rtsp-url rtsp://<nano-b01-ip>:8554/robot \
  --websocket-url ws://<대시보드-ip>:<port> \
  --confidence 0.25 --iou 0.45 --publish-fps 10
```

환경변수로도 지정 가능 (둘 다 없으면 아래 기본값 사용):

| 환경변수 | 대응 옵션 | 기본값 |
|---|---|---|
| `SILOROBOT_MODEL` | `--model` | `artifacts/cc_seg_v1_fp16.engine` |
| `SILOROBOT_RTSP_URL` | `--rtsp-url` | `rtsp://100.121.144.38:8554/robot` |
| `SILOROBOT_WS_URL` | `--websocket-url` | `ws://100.74.141.112:8765` |

### 3-3. 옵션 전체

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--confidence` | 0.25 | Colab 평가 임계값과 동일. 오검출 많으면 올리기 |
| `--iou` | 0.45 | NMS IoU. 겹친 인스턴스가 과하게 합쳐지면 낮추기 |
| `--image-size` | 640 | 학습·export와 반드시 동일 |
| `--publish-fps` | 10.0 | 추론·전송 빈도 (캡처 자체는 계속하되 이 간격보다 짧으면 스킵). 부하 크면 낮추기 |
| `--mask-points` | 60 | 폴리곤 최대 점 수(대역폭 절약). 대시보드가 느려지면 낮추기 |
| `--log-dir` | `logs` | 탐지결과 JSONL 저장 위치 |

---

## 4. 문제 해결

| 증상 | 확인/조치 |
|---|---|
| `torch.cuda.is_available()` False | 잘못된 torch wheel — JetPack 버전 다시 확인 후 Jetson 전용 wheel 재설치 |
| RTSP 연결 실패 | `python3 -c "import cv2; print(cv2.getBuildInformation())" \| grep -i ffmpeg` 로 FFmpeg 지원 확인. 안 되면 시스템 `python3-opencv`(GStreamer 포함)로 교체 필요 |
| 엔진 export 중 OOM | `workspace` 값 낮추기(2 등), 다른 프로세스 종료 |
| export는 됐는데 예측이 이상함 | `python -m inference.main --dry-run`으로 통신부터 확인 → 실제 모델로 실행 후 로컬 `yolo predict` 결과와 육안 비교 |
| 라벨이 "crack"/"corrosion"이 아니라 이상하게 나옴 | `.engine`이 클래스 메타데이터를 잃은 경우 — `.pt`로 먼저 테스트해서 `result.names`가 `{0:'crack',1:'corrosion'}`인지 확인 |
| 지연시간이 잴 때마다 다름 | `sudo nvpmodel -m 0 && sudo jetson_clocks` 안 했을 가능성 |

---

## 5. 파일 구성

| 파일 | 역할 |
|---|---|
| `main.py` | CLI 진입점 (인자·환경변수 파싱) |
| `pipeline.py` | RTSP 수신 → 추론 → WebSocket 전송 (핵심 로직) |
| `messages.py` | WebSocket 메시지 스키마 (`Detection`: bbox + `polygon`) |
| `logging_jsonl.py` | 탐지결과 날짜별 JSONL 저장 |
| `requirements.txt` | 필요 pip 패키지 (설치 순서·이유 주석 포함) |
