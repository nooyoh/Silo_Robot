<div align="center">

# 🛢️ 사일로봇 (Silo Robot)

**가변 자력 기반의 곡면 적응형 궤도를 활용한 철제 구조물 안전 점검 로봇**

2026 한이음 드림업 · 스마트해운물류 X ICT 멘토링

![STM32](https://img.shields.io/badge/STM32-F401RE-03234B?logo=stmicroelectronics&logoColor=white)
![Jetson](https://img.shields.io/badge/Jetson-Nano%20B01%20%7C%20Orin%20Nano-76B900?logo=nvidia&logoColor=white)
![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4B-A22846?logo=raspberrypi&logoColor=white)
![ROS2](https://img.shields.io/badge/ROS2-Eloquent-22314E?logo=ros&logoColor=white)
![Qt](https://img.shields.io/badge/Qt-6-41CD52?logo=qt&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8s-seg-00FFFF)

</div>

---

## 📌 개요

사일로·저장 탱크 같은 철제 구조물의 점검은 **밀폐공간 진입(질식)** 과 **고소작업(추락)** 위험이 크고, 비계·로프 설치에 많은 시간과 비용이 듭니다. 드론은 바람과 비행시간 때문에 벽면에 가까이 붙어 촬영하기 어렵습니다.

사일로봇은 **자력으로 철제 벽면에 붙어 이동하는 궤도형 로봇**입니다. 작업자가 들어가기 전에 벽면을 가까이서 촬영하고, AI로 균열·부식 의심 위치를 찾아 기록합니다.

| 구분 | 육안 점검 | 점검용 드론 | **사일로봇** |
|---|---|---|---|
| 벽면 접근 | 비계·로프, 작업자 직접 접근 | 비접촉 비행 | **자력 부착 주행** |
| 곡면 대응 | 작업자 임의 대응 | 근접 유지 곤란 | **스프링 쇼바로 궤도 각도 자동 추종** |
| 부착력 조절 | – | – | **할바흐 배열 공극 조절** |
| 이상 시 대응 | 작업자 판단 | 조종자 판단 | **복합 조건 자동 정지 + 명시적 수동 해제** |
| 점검 결과 | 수기 기록·사진 | 영상 파일 | **영상·위치·센서값을 하나의 record로 저장** |
| 통신 단절 | – | 무선 조종 | **300 ms 페일세이프** |

> 법정 가스측정·환기·보호구 등 안전조치를 대체하지 않고, 작업자 투입 판단을 돕는 **선행 점검 보조 장비**입니다.

## 🎬 동작영상

<!-- 동작영상 추가 예정 -->

## 🏗️ 시스템 아키텍처

### S/W 구성도

![S/W 구성도](docs/4.%20자료/05.%20결과보고서%20그림/SW_구성도.png)

### H/W 구성도

![H/W 구성도](docs/4.%20자료/05.%20결과보고서%20그림/HW_구성도.png)

### 서비스 흐름도

![서비스 흐름도](docs/4.%20자료/05.%20결과보고서%20그림/서비스_흐름도.png)

**역할 분리** — AI 연산이나 관제 통신에 문제가 생겨도 실시간 제어와 안전 기능은 독립적으로 동작하도록 나눴습니다.

| 장치 | 담당 |
|---|---|
| STM32 F401RE | 모터 4채널 PWM·방향, 엔코더·거리센서 수집, 비상정지 래치, 통신 단절 시 출력 차단 |
| Jetson Nano B01 | ROS2 노드 8개 운용, IMU·오도메트리·경로 추종, CSI 카메라 RTSP 송출, 장치 간 통신 |
| Jetson Orin Nano Super | RTSP 수신 → YOLOv8s-seg(TensorRT) 추론 → 탐지 결과 전송 |
| Raspberry Pi 4B | 7인치 터치 관제 화면, 주행·비상정지, 경로 생성, 점검기록 관리 |

## 🛠️ 기술스택

| 분야 | 사용 기술 |
|---|---|
| 언어 | C, C++, Python, QML |
| 펌웨어 | STM32 HAL (베어메탈), ARM GCC, STM32CubeIDE |
| 로봇 SW | ROS2 Eloquent, GStreamer RTSP Server |
| AI | Ultralytics YOLOv8s-seg, ONNX, TensorRT, Google Colab Pro |
| 관제 GUI | Qt 6 (Quick · Multimedia · WebSockets), CMake |
| 통신 | UART (ST-LINK VCP, 115200bps), WebSocket, RTSP, Tailscale |

## 🔩 사용 하드웨어

| 분류 | 부품 | 용도 |
|---|---|---|
| 연산 | STM32 NUCLEO-F401RE | 모터 제어·안전 정지 |
| | Jetson Nano B01 | ROS2·센서 융합·영상 송출 |
| | Jetson Orin Nano Super | AI 결함 탐지 |
| | Raspberry Pi 4 + 7인치 터치스크린 | 관제 콘솔 |
| 구동 | WGM40-3150-1280E 웜기어 엔코더 모터 ×4 | 좌·우 궤도 독립 구동 |
| | DFR0601 듀얼채널 모터 드라이버 ×2 | 모터 2개씩 구동 |
| 센서 | IMX219 CSI 카메라 + COB LED | 벽면 근접 촬영 |
| | WT901C 9축 IMU | 회전각 보정, 이탈 위험 판단 |
| | GP2Y0A51SK0F 거리센서 ×3 | 벽면 3점 밀착 상태 감시 |
| 부착·기구 | 할바흐 배열 자석 | 공극 조절로 부착력 가변 |
| | 알루미늄 프로파일, 3D 프린터 출력물 | 프레임·궤도·관절·서스펜션·자석 홀더 (직접 CAD 설계) |
| 전원 | 11.1V Li-Po ×2, Jetson Nano UPS, DC/DC, 퓨즈 | 모터/연산 전원 분리·보호 |

<p align="center">
  <img src="docs/4.%20자료/02.%20보고서%20구성도/구성도_자료/기구시제품.jpg" width="45%" alt="기구 시제품"/>
</p>

## ✨ 주요 기능

**🧲 하드웨어**
- **가변 자력 부착** — 할바흐 배열 자석의 수직 위치를 바꿔 공극을 조절, 자석 교체 없이 부착력과 탈착 편의성을 조절
- **곡률 적응형 궤도** — 스프링 쇼바 서스펜션으로 평면·곡면에 따라 좌·우 궤도 각도가 자동으로 바뀜
- **좌·우 독립 구동** — 속도 차 조향과 정지 상태 제자리 회전

**💻 소프트웨어**
- **원격 주행** — 800×480 터치 화면에서 양손 멀티터치로 전후진·조향 동시 입력, 비상정지
- **반자율 전면점검** — 사일로 크기·점검폭·중첩률·안전여백을 반영한 2D 전개도 지그재그 경로 생성, 엔코더+IMU 오도메트리로 경로 추종
- **AI 결함 탐지** — 균열(crack)·부식(corrosion) 세그멘테이션 결과를 실시간 영상 위에 재인코딩 없이 오버레이
- **점검 증거기록** — 프레임·촬영시각·경로 위치·센서값·탐지 결과를 같은 record ID로 이미지+JSONL 저장, 미수신 데이터는 임의 생성하지 않고 빈값으로 명시

## 🛡️ 안전 설계

| 상황 | 감지 조건 | 대응 | 재개 조건 |
|---|---|---|---|
| 밀착 불균형·이탈 위험 | 3점 거리 편차·증가 + IMU 변화 | 단일 이상은 경고, 복합 이상 지속 시 경로 정지·모터 차단 | 운용자 명시적 해제 |
| 통신 단절 | WebSocket/UART 타임아웃 | Nano B01 → STM32 단계적 정지, 300 ms 후 PWM 차단 | 연결 복구 후 운용자 재승인 |
| 부팅·재연결 | 장치 기동/UART 재연결 | 정지 상태로 시작 | 운용자 명시적 해제 |

벽면·천장에서는 중력 방향이 바뀌어 절대 Roll·Pitch로는 위험을 판단할 수 없기 때문에, **IMU 동적 변화량 + 거리센서 3점 평균·편차**를 함께 사용합니다.

## 📁 파일 구조

```
Silo_Robot/
├─ docs/                  # 설계 문서·시험 로그·보고서 (Obsidian Vault)
│  ├─ 1. 로그/            #   날짜별 개발·시험 기록
│  ├─ 2. 하드웨어/        #   아키텍처·구동계·센서·전원·배선도
│  ├─ 3. 소프트웨어/      #   STM32·젯슨·대시보드 명세, 노드·토픽·메시지 정본
│  ├─ 4. 자료/            #   결과보고서 그림·구성도·캡처·시장조사·원본 계획서
│  └─ 5. 보고서/          #   공모전 보고서·제작설계서
├─ stm32-f401re/          # STM32 모터 제어 펌웨어 (App/, Core/, ThirdParty/)
├─ jetson-nano-b01/       # ROS2 패키지 silorobot_nano, 실행 스크립트, 오프로봇 검증 도구
├─ jetson-orin-nano/      # YOLOv8s-seg 데이터 전처리·학습 노트북·Orin 추론 파이프라인
└─ rpi4-dashboard/        # Qt 6 관제 콘솔 (qml/, src/, systemd/)
   └─ webcam_demo/        #   PC 웹캠 + 대시보드 로컬 시연용 데모
```

각 모듈의 상세 빌드·실행 방법은 모듈별 `README.md`를 참고하세요.

## 🚀 빠른 시작

```bash
# STM32 — STM32CubeIDE: File > Import > Existing Projects into Workspace → stm32-f401re/

# Jetson Nano B01
cd jetson-nano-b01
bash scripts/silorobot.sh build
bash scripts/silorobot.sh preflight
ros2 launch silorobot_nano robot.launch.py

# Jetson Orin Nano (모델은 Orin에서 TensorRT 엔진으로 빌드)
cd jetson-orin-nano
python -m inference.main --model artifacts/cc_seg_v1_fp16.engine \
  --rtsp-url rtsp://<nano-ip>:8554/robot --websocket-url ws://<rpi4-ip>:8765

# RPi4 관제 콘솔
cd rpi4-dashboard
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j2
./build/silorobot-dashboard --rtsp rtsp://<nano-ip>:8554/robot
```

## 💻 개발 환경

| 구분 | 내용 |
|---|---|
| OS | Nano B01: Ubuntu 18.04 · RPi4: Raspberry Pi OS 64-bit · Orin: JetPack 기반 Linux |
| IDE / 빌드 | STM32CubeIDE, CMake, ROS2 colcon |
| 학습 | Google Colab Pro → ONNX → Orin 현지 TensorRT 엔진 빌드 |
| 네트워크 | Tailscale (장치 간 원격 접속) |
| 형상관리 | GitHub `SiloRobot` 조직 (장치별 저장소 4개 → 본 저장소로 통합) |

## 🤝 팀 협업

| 이름 | 역할 | 담당 |
|---|---|---|
| 안민철 | 팀장 | 전원 아키텍처·일정·문서 관리, 장치 간 통신 규격 정의, 시스템 통합 |
| 김상우 | 팀원 | 곡률 적응형 궤도·서스펜션 CAD 설계, 3D 출력물 검증 |
| 송관웅 | 팀원 | 전원·모터 드라이버·센서·제어기 배선 설계, HW·SW 연결 |
| 조경찬 | 팀원 | 프레임·구동부·자석 부착 구조 제작, 최종 조립, 부착력 시험 |
| 이호윤 | 팀원 | 카메라 영상 파이프라인, 균열 데이터 정제, YOLO 모델 학습, Orin 추론 환경 구축 |

**협업 방식**
- 💬 **Discord** 상시 소통, 📋 **Jira** 일정·작업 배분, 정기 멘토링과 통합시험
- 📝 **Obsidian Vault**(`docs/`)에 결정로그·트러블슈팅·운영기록·날짜별 시험 기록 축적
- 🔗 UART·WebSocket·RTSP 메시지 구조를 공통 문서(`docs/3. 소프트웨어/07. 구현 계약`)로 관리하고, 인터페이스가 바뀌면 관련 코드와 문서를 함께 갱신

## 🧩 트러블슈팅

| 문제 | 원인 | 해결 |
|---|---|---|
| 벽면·천장 전환을 위험으로 오판 | 지상 로봇식 절대 Roll·Pitch 임계값 | IMU 변화량 + 거리센서 3점 평균·편차 결합 판정으로 재설계 |
| 관제 명령이 와도 모터 미구동 | STM32는 정지 상태, Nano 브리지는 해제 상태로 부팅 | Nano도 초기·재연결 시 정지 상태로 간주, 명시적 해제 시에만 STM32에 해제 전송 |
| 반자율 주행 시 제자리 회전·역조향 | 엔코더 부호·조향 부호·좌표 기준점 불일치 | 부호 규칙 통일, 경로 시작점을 현재 오도메트리에 정렬, 역방향 자동검증 추가 |
| RTSP 최초 연결 실패 후 미복구 | 관제 프로그램이 카메라 서버보다 먼저 기동 | 영상 연결상태 표시와 재연결 기능 추가 |

자세한 기록은 `docs/03. 트러블슈팅.md`를 참고하세요.

## 📈 개발 현황

- RPi4 → Nano B01 → STM32 → 모터 4개 제어 경로와 CSI 카메라 실시간 영상 송출을 실제 장비에서 확인
- 반자율 전면점검 코드 **오프로봇 검증 63개 통과**
- 경로 생성과 이미지·JSONL 점검기록 기능을 관제 콘솔에 통합

## 🌏 기대효과 및 활용 분야

- **작업자** — 밀폐공간·고소 벽면 직접 진입을 줄여 질식·추락·유해물질 노출 위험 저감
- **시설 운영자** — 비계 설치 전 선행 점검, 결함 위치 기록으로 보수 우선순위 판단과 유지보수 이력 관리
- **적용 분야** — 항만 곡물·사료 사일로, 석유화학·산업용 저장 탱크, 강재 교량·선박·해양플랜트 등 철제 구조물
