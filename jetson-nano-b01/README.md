# SiloRobot Jetson Nano B01

ROS 2 robot-brain package for dashboard networking, STM32/IMU bridges, safety monitoring,
odometry, coverage planning and low-speed path following. AI inference lives in `jetson-orin-nano/` of this repository.

All bring-up and calibration commands are consolidated into one tool:

```bash
bash scripts/silorobot.sh menu
```

## Build and preflight

Install the non-ROS runtime packages once on the Nano:

```bash
sudo apt update
sudo apt install python3-serial python3-websockets python3-gi gir1.2-gst-rtsp-server-1.0
```

```bash
bash scripts/silorobot.sh build
bash scripts/silorobot.sh preflight
```

Environment overrides: `STM_PORT`, `IMU_PORT`, `DASHBOARD_HOST`, `WS_PORT`, `ROS_SETUP`.

## Start with a tuning profile

```bash
source install/setup.bash
ros2 launch silorobot_nano robot.launch.py
```

The default is `config/bootstrap.yaml`, `armed=false`, and
`distance_calibration_confirmed=false`. The bootstrap odometry uses the WGM40 datasheet/STL
estimate (both encoder scales negative, 0.294 m track width), so it can run a small lifted-track
HIL test but is not a wall-driving calibration. Copy `measured.template.yaml` to a measured profile,
replace the estimates, rebuild, then launch with:

```bash
ros2 launch silorobot_nano robot.launch.py \
  profile_file:=$PWD/src/silorobot_nano/config/measured.yaml \
  distance_calibration_confirmed:=true
```

Do not set `armed=true` until the measured profile passes the external-disturbance procedure.

For an explicit demonstration run before the distance sensors/IMU safety profile is ready:

```bash
sudo systemctl stop silorobot-nano.service
bash scripts/silorobot.sh demo-drive
```

The `demo-drive` command requires typing `DEMO` in an interactive terminal. It
permits dashboard manual drive and short autonomous routes with `armed=false`,
`require_distance=false`, and the explicit unarmed-autonomy override. It does
not disable the dashboard emergency stop, STM32 boot latch, 300 ms command
timeout, or enabled low-battery stop. The old `bench-autonomy` command remains
as a compatibility alias and requires typing `BENCH`.

For a time-critical filming fallback, `demo-square` publishes a 0.5 x 0.5 m
route plus a synchronized live marker/progress timeline to the normal planner
screen while sending open-loop motor commands. Visible execution is 10 seconds:

```bash
sudo systemctl stop silorobot-nano.service
bash scripts/silorobot.sh build
bash scripts/silorobot.sh demo-square
```

The default timing is four 1.5 s straight legs, four 0.6 s turns and eight
0.2 s settling gaps:

```bash
SQUARE_SIZE_M=0.5 SQUARE_SIDE_SECONDS=1.5 SQUARE_TURN_SECONDS=0.6 \
  bash scripts/silorobot.sh demo-square
```

This mode is for filming UI/motor integration on a restrained robot or a clear,
level floor only. Dashboard emergency stop and the STM32 300 ms timeout remain
active. The displayed 0.5 m scale is a synchronized presentation timeline, not
encoder-measured distance or evidence of autonomous path following.

## Distance calibration

Hold a target at each distance and collect at least five seconds:

```bash
bash scripts/silorobot.sh distance 5
```

The report prints three C LUT initializers. Replace the three tables in STM32 `Core/Src/main.c`.

## Battery telemetry

The bridge parses STM32 frame `0xBE` into representative low-pack voltage plus per-pack millivolts
and flags. Until both 1/5 divider circuits are wired and the firmware is built with
`BATTERY_MONITOR=1`, the dashboard intentionally shows `--`; floating ADC pins are never shown as
real battery values. Enabled monitoring refuses STOP release while either pack is invalid and the
STM32 owns the 9.9 V low-voltage stop latch.

## Odometry calibration

Reset/start the robot, collect while moving exactly 1 m, then report:

```bash
bash scripts/silorobot.sh straight 1.0 20
```

For a measured full rotation, use the measured left/right scales:

```bash
bash scripts/silorobot.sh turn 6.283185307 0.0000144 0.0000145 20
```
## 부팅 자동 실행 — 전원만으로 운용

Nano B01은 한 번 설정하면 키보드·마우스·터미널 없이 전원 인가만으로 로봇 두뇌 전체를 시작한다.
`systemd/silorobot-nano.service`는 `jetson` 사용자(`dialout`, `video` 권한)로 실행되며, 네트워크와
Tailscale이 준비된 뒤 다음을 자동 기동한다.

- CSI 카메라 RTSP: `rtsp://<Nano Tailscale IP>:8554/robot`
- Pi 대시보드 WebSocket 브릿지
- STM32·IMU 자동 재접속 브릿지
- safety supervisor, odometry, coverage planner, path follower

### 최초 1회 설치

Nano에서 아래를 한 번 실행하고 `jetson`의 sudo 비밀번호를 입력한다.

```bash
cd ~/jetson-nano-b01
sudo install -m 644 systemd/silorobot-nano.service /etc/systemd/system/silorobot-nano.service
sudo systemctl daemon-reload
sudo systemctl enable --now silorobot-nano.service
```

정상 설치 확인:

```bash
systemctl is-enabled silorobot-nano.service  # enabled
systemctl is-active silorobot-nano.service   # active
```

이후에는 Nano 전원만 켜면 된다. STM32나 IMU가 아직 연결되지 않은 경우에도 서비스는 종료되지 않고
해당 포트를 재시도한다.

### 코드 업데이트 뒤 적용

새 코드를 반영한 경우에는 빌드 후 서비스를 재시작한다.

```bash
cd ~/jetson-nano-b01
git pull
source /opt/ros/eloquent/setup.bash
colcon build --symlink-install --packages-select silorobot_nano
sudo systemctl restart silorobot-nano.service
```

### 상태 확인·문제 진단

```bash
systemctl --no-pager --full status silorobot-nano.service
journalctl -u silorobot-nano.service -f
```

정상 로그에는 `RTSP ready`와 `Connected to dashboard WebSocket`이 나타난다. 서비스 중지·재시작은
`sudo systemctl stop|restart silorobot-nano.service`를 사용한다.
