#!/usr/bin/env bash
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
# Start the complete Nano B01 robot brain after system boot.

# ROS2 Eloquent setup.bash reads optional unset variables, so nounset (-u)
# cannot be enabled in this process.
set -eo pipefail

source /opt/ros/eloquent/setup.bash
source /home/jetson/jetson-nano-b01/install/setup.bash

# require_distance:=false — 거리센서 3점이 아직 물리적으로 안 달려 있다.
#
# 이 값이 true(launch 기본값)이면 safety_supervisor가 거리 데이터를 영원히 기다리며
# 상태를 OFFLINE에 붙들어 둔다. 그러면 정지 해제도 거부되고 route_start도 거부돼서
# 전원만 켜서는 로봇이 아예 안 움직인다. 센서가 없는 지금은 이 게이트가 보호하는
# 대상이 없고 차단만 하므로 꺼둔다. 나머지 안전장치(STM32 정지 래치, 300ms 통신
# 페일세이프, 비상정지, armed=false)는 그대로 살아 있다.
#
# ★ 거리센서를 실제로 배선하면 이 줄을 지워서 true로 되돌릴 것.
#   ([[2. 하드웨어/05. 배선도]] §5, §8 검증 절차)
# 자율주행은 별도 안전게이트로 armed=true를 요구한다. 구동계를 지그에 고정한 HIL에서만
# launch 인자 allow_unarmed_autonomy:=true를 수동으로 추가한다.
exec ros2 launch silorobot_nano robot.launch.py \
    use_camera:=true \
    dashboard_uri:=ws://100.74.141.112:8765 \
    require_distance:=false \
    allow_unarmed_autonomy:=false
