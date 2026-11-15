#!/usr/bin/env bash
set -eo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ros_setup="${ROS_SETUP:-/opt/ros/eloquent/setup.bash}"
stm_port="${STM_PORT:-/dev/ttyACM0}"
imu_port="${IMU_PORT:-/dev/ttyTHS1}"
dashboard_host="${DASHBOARD_HOST:-100.74.141.112}"
ws_port="${WS_PORT:-8765}"
calibration_dir="${CALIBRATION_DIR:-$repo_dir/calibration}"

usage() {
  cat <<'EOF'
SiloRobot unified bring-up tool

usage: bash scripts/silorobot.sh COMMAND [ARGS]

commands:
  menu                         interactive menu
  build                        ROS 2 colcon build
  preflight                    ports, tools, network and ROS topics check
  run [extra launch args...]   launch the complete Nano stack
  demo-drive                   sensor-bypass demo run (manual + autonomy)
  demo-square                  10 s, 0.5 x 0.5 m planner-screen filming demo
  bench-autonomy              compatibility alias for demo-drive
  distance [seconds]           interactive 20..150 mm, 7-point ADC collection + LUT report
  straight [meters] [seconds]  collect straight run + meters/count report (default 1 m, 20 s)
  turn RAD LEFT_SCALE RIGHT_SCALE [seconds]
                               collect rotation + track-width report
  report-distance [csv]        recalculate LUT from an existing CSV
  test                         code-only protocol/syntax tests available on Nano

environment overrides:
  ROS_SETUP STM_PORT IMU_PORT DASHBOARD_HOST WS_PORT CALIBRATION_DIR
EOF
}

source_ros() {
  if [[ ! -f "$ros_setup" ]]; then
    echo "ROS setup not found: $ros_setup" >&2
    exit 2
  fi
  source "$ros_setup"
}

source_workspace() {
  source_ros
  if [[ ! -f "$repo_dir/install/setup.bash" ]]; then
    echo 'workspace is not built; run: bash scripts/silorobot.sh build' >&2
    exit 2
  fi
  source "$repo_dir/install/setup.bash"
}

build_workspace() {
  source_ros
  cd "$repo_dir"
  colcon build --symlink-install --packages-select silorobot_nano
  source install/setup.bash
  python3 -m compileall -q src/silorobot_nano/silorobot_nano
  echo "build OK: $repo_dir/install"
}

preflight() {
  local failures=0 topics=''
  source_ros
  pass() { printf '[PASS] %s\n' "$1"; }
  fail() { printf '[FAIL] %s\n' "$1"; failures=$((failures + 1)); }
  warn() { printf '[WARN] %s\n' "$1"; }

  for command in python3 ros2 colcon; do
    command -v "$command" >/dev/null 2>&1 && pass "$command available" || fail "$command missing"
  done
  python3 -c 'import serial, websockets' >/dev/null 2>&1 \
    && pass 'Python serial/websockets modules available' \
    || fail 'Python module missing: install python3-serial and python3-websockets'
  python3 -c "import gi; gi.require_version('Gst', '1.0'); gi.require_version('GstRtspServer', '1.0'); from gi.repository import Gst, GstRtspServer" >/dev/null 2>&1 \
    && pass 'GStreamer RTSP Python bindings available' \
    || fail 'GStreamer RTSP bindings missing: install python3-gi and gir1.2-gst-rtsp-server-1.0'
  [[ -r "$stm_port" && -w "$stm_port" ]] && pass "STM32 port $stm_port" || fail "STM32 port unavailable: $stm_port"
  [[ -r "$imu_port" && -w "$imu_port" ]] && pass "IMU port $imu_port" || warn "IMU port unavailable: $imu_port"
  groups | grep -qw dialout && pass 'user belongs to dialout' || fail 'user is not in dialout group'
  [[ -f "$repo_dir/install/setup.bash" ]] && pass 'workspace is built' || fail 'workspace is not built'
  timeout 2 bash -c "</dev/tcp/$dashboard_host/$ws_port" >/dev/null 2>&1 \
    && pass "dashboard TCP $dashboard_host:$ws_port" \
    || warn "dashboard TCP unavailable: $dashboard_host:$ws_port"
  if [[ -f "$repo_dir/install/setup.bash" ]]; then
    source "$repo_dir/install/setup.bash"
    topics="$(timeout 3 ros2 topic list 2>/dev/null || true)"
    for topic in /silorobot/stm32_connected /silorobot/distance_adc \
                 /silorobot/wheel_counts /silorobot/battery_pack_mv; do
      grep -qx "$topic" <<<"$topics" && pass "topic $topic" || warn "topic not active: $topic"
    done
  fi
  if (( failures > 0 )); then
    echo "preflight failed: $failures critical problem(s)" >&2
    return 1
  fi
  echo 'preflight passed (WARN items may require optional hardware/network)'
}

run_robot() {
  source_workspace
  exec ros2 launch silorobot_nano robot.launch.py "$@"
}

run_demo_drive() {
  local confirmation_word="${1:-DEMO}"
  if [[ ! -t 0 ]]; then
    echo 'demo-drive requires an interactive terminal confirmation' >&2
    exit 2
  fi
  cat <<'EOF'
WARNING: DEMO DRIVE MODE
Disabled: distance/IMU automatic safety decisions and the normal armed-autonomy gate.
Still active: dashboard emergency stop, STM32 boot latch, 300 ms command timeout,
and low-battery stop when the battery monitor is wired/enabled.
Use only with lifted tracks or a clear, level demo area. Never use this mode on a wall.
EOF
  printf 'Type %s to continue: ' "$confirmation_word"
  read -r confirmation
  if [[ "$confirmation" != "$confirmation_word" ]]; then
    echo 'cancelled'
    exit 2
  fi
  source_workspace
  if systemctl is-active --quiet silorobot-nano.service 2>/dev/null; then
    echo 'Stop the boot service first to avoid duplicate ROS publishers:' >&2
    echo '  sudo systemctl stop silorobot-nano.service' >&2
    exit 2
  fi
  exec ros2 launch silorobot_nano robot.launch.py \
    armed:=false \
    require_distance:=false \
    distance_calibration_confirmed:=false \
    allow_unarmed_autonomy:=true
}

run_demo_square() {
  if [[ ! -t 0 ]]; then
    echo 'demo-square requires an interactive terminal confirmation' >&2
    exit 2
  fi
  cat <<'EOF'
WARNING: 10 SECOND, 0.5 x 0.5 m PLANNER-SCREEN DEMO
The dashboard route, marker and progress are a synchronized filming timeline.
Physical motion is open-loop and does not prove measured 0.5 m travel.
The planner, odometry and distance/IMU decisions are bypassed for motor control.
Dashboard emergency stop and the STM32 300 ms command timeout remain active.
Use only on a clear, level floor with at least 1.5 x 1.5 m clearance. Never use on a wall.
Do not touch the drive joystick while it runs; use only emergency stop or Ctrl+C.
EOF
  printf 'Type SQUARE to continue: '
  read -r confirmation
  if [[ "$confirmation" != 'SQUARE' ]]; then
    echo 'cancelled'
    exit 2
  fi
  source_workspace
  if systemctl is-active --quiet silorobot-nano.service 2>/dev/null; then
    echo 'Stop the boot service first to avoid duplicate ROS publishers:' >&2
    echo '  sudo systemctl stop silorobot-nano.service' >&2
    exit 2
  fi
  exec ros2 launch silorobot_nano robot.launch.py \
    use_camera:="${USE_CAMERA:-false}" \
    armed:=false \
    require_distance:=false \
    distance_calibration_confirmed:=false \
    allow_unarmed_autonomy:=true \
    demo_square:=true \
    demo_square_size_m:="${SQUARE_SIZE_M:-0.5}" \
    demo_square_side_seconds:="${SQUARE_SIDE_SECONDS:-1.5}" \
    demo_square_turn_seconds:="${SQUARE_TURN_SECONDS:-0.6}" \
    demo_square_straight_command:="${SQUARE_STRAIGHT_COMMAND:-50.0}" \
    demo_square_turn_command:="${SQUARE_TURN_COMMAND:-40.0}"
}

collect_distance() {
  local duration="${1:-5}" output="$calibration_dir/distance-$(date +%Y%m%d-%H%M%S).csv"
  source_workspace
  mkdir -p "$calibration_dir"
  for mm in 20 30 50 70 100 120 150; do
    read -r -p "표적을 ${mm} mm에 고정한 뒤 Enter를 누르세요: "
    ros2 run silorobot_nano calibration_collector \
      --target-mm "$mm" --duration "$duration" --output "$output"
  done
  echo '--- recommended STM32 LUT ---'
  ros2 run silorobot_nano calibration_report "$output" --distance-lut
  echo "raw CSV: $output"
}

collect_straight() {
  local meters="${1:-1.0}" duration="${2:-20}"
  local output="$calibration_dir/straight-${meters}m-$(date +%Y%m%d-%H%M%S).csv"
  source_workspace
  mkdir -p "$calibration_dir"
  read -r -p "카운트를 확인하고 ${meters} m 직진 준비 후 Enter를 누르세요: "
  ros2 run silorobot_nano calibration_collector --duration "$duration" --output "$output"
  ros2 run silorobot_nano calibration_report "$output" --distance-m "$meters"
  echo "raw CSV: $output"
}

collect_turn() {
  if (( $# < 3 )); then
    echo 'turn requires: RADIANS LEFT_SCALE RIGHT_SCALE [SECONDS]' >&2
    exit 2
  fi
  local radians="$1" left_scale="$2" right_scale="$3" duration="${4:-20}"
  local output="$calibration_dir/turn-$(date +%Y%m%d-%H%M%S).csv"
  source_workspace
  mkdir -p "$calibration_dir"
  read -r -p "제자리 회전 준비 후 Enter를 누르세요: "
  ros2 run silorobot_nano calibration_collector --duration "$duration" --output "$output"
  ros2 run silorobot_nano calibration_report "$output" \
    --turn-radians "$radians" --left-scale "$left_scale" --right-scale "$right_scale"
  echo "raw CSV: $output"
}

run_tests() {
  source_ros
  cd "$repo_dir"
  python3 -m compileall -q src/silorobot_nano
  if command -v pytest >/dev/null 2>&1; then
    pytest -q src/silorobot_nano/test
  else
    echo '[WARN] pytest missing; compileall only'
  fi
}

menu() {
  while true; do
    cat <<'EOF'

1) build        2) preflight      3) run
4) distance     5) straight 1 m   6) turn 360 deg
7) test         8) demo drive     9) demo square     0) exit
EOF
    read -r -p '선택: ' choice
    case "$choice" in
      1) build_workspace ;;
      2) preflight ;;
      3) run_robot ;;
      4) collect_distance 5 ;;
      5) collect_straight 1.0 20 ;;
      6)
        read -r -p 'left meters/count: ' left
        read -r -p 'right meters/count: ' right
        collect_turn 6.283185307 "$left" "$right" 20
        ;;
      7) run_tests ;;
      8) run_demo_drive DEMO ;;
      9) run_demo_square ;;
      0) return ;;
      *) echo '잘못된 선택입니다.' ;;
    esac
  done
}

command="${1:-menu}"
if (( $# > 0 )); then shift; fi
case "$command" in
  menu) menu ;;
  build) build_workspace ;;
  preflight) preflight ;;
  run) run_robot "$@" ;;
  demo-drive) run_demo_drive DEMO ;;
  demo-square) run_demo_square ;;
  bench-autonomy) run_demo_drive BENCH ;;
  distance) collect_distance "$@" ;;
  straight) collect_straight "$@" ;;
  turn) collect_turn "$@" ;;
  report-distance)
    source_workspace
    report_file="${1:-}"
    if [[ -z "$report_file" ]]; then
      report_file="$(find "$calibration_dir" -maxdepth 1 -type f -name 'distance-*.csv' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2-)"
    fi
    [[ -n "$report_file" ]] || { echo 'no distance CSV found' >&2; exit 2; }
    ros2 run silorobot_nano calibration_report "$report_file" --distance-lut
    ;;
  test) run_tests ;;
  help|-h|--help) usage ;;
  *) usage >&2; exit 2 ;;
esac
