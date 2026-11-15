# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0

import time

from silorobot_nano.coverage_planner import make_plan
from silorobot_nano.path_follower import PathFollower
from silorobot_nano.safety_supervisor import STM_FLAG_STOP_LATCHED
from silorobot_nano.safety_supervisor import SafetySupervisor
from silorobot_nano.stm32_uart_bridge import Stm32UartBridge


class CapturePublisher:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


def test_nano_command_frame_matches_stm32_contract():
    assert Stm32UartBridge._make_command_frame(1, -100, 50) == bytes(
        [0xAA, 0x01, 0x9C, 0x32, 0xAF, 0x55])


def test_coverage_plan_stays_inside_margin():
    plan = make_plan({
        'area': {'surface': 'RECTANGLE', 'width_m': 12, 'height_m': 8},
        'scan_width_m': 0.4,
        'overlap_ratio': 0.2,
        'safety_margin_m': 0.2,
        'start_corner': 'TOP_LEFT',
    }, 'TEST')
    assert plan['waypoints']
    assert all(0.2 <= point['x'] <= 11.8 for point in plan['waypoints'])
    assert all(0.2 <= point['y'] <= 7.8 for point in plan['waypoints'])
    cross_key = 'x' if plan['orientation'] == 'VERTICAL' else 'y'
    lanes = sorted(set(point[cross_key] for point in plan['waypoints']))
    spacing = 0.4 * (1.0 - 0.2)
    assert all(right - left <= spacing + 1e-9
               for left, right in zip(lanes, lanes[1:]))


def test_path_follower_aligns_in_place_and_stops_at_last_waypoint():
    follower = PathFollower.__new__(PathFollower)
    follower._pose = {'x': 0.0, 'y': 0.0, 'theta': 0.0}
    follower._plan = {'waypoints': [{'x': 0.0, 'y': 1.0}]}
    follower._waypoint_index = 0
    follower._radius = 0.05
    follower._align_threshold = 0.35
    follower._heading_deadband = 0.05
    follower._heading_gain = 1.0
    follower._max_throttle = 15.0
    follower._max_turn = 20.0
    follower._min_effective_throttle = 15.0
    follower._min_effective_turn = 20.0
    follower._progress_pose = None
    follower._progress_at = None
    follower._progress_timeout = 4.0
    follower._min_progress_m = 0.005
    follower._min_progress_rad = 0.03
    follower._last_debug_log = time.monotonic()
    follower._anchor = None
    follower._state = 'RUNNING'
    follower._mode = 'AUTO'
    follower._drive_publisher = CapturePublisher()

    follower._follow_once()
    align = follower._drive_publisher.messages[-1]
    assert align.linear.x == 0.0
    # Hardware drive convention is clockwise-positive, opposite ROS yaw.
    assert align.angular.z < 0.0

    follower._pose = {'x': 0.0, 'y': 1.0, 'theta': 1.57}
    follower._follow_once()
    stopped = follower._drive_publisher.messages[-1]
    assert stopped.linear.x == 0.0 and stopped.angular.z == 0.0
    assert follower._state == 'COMPLETE'
    assert follower._mode == 'MANUAL'


def test_release_requires_fresh_physical_stm32_latch():
    safety = SafetySupervisor.__new__(SafetySupervisor)
    safety._stm_connected = True
    safety._stm_flags = STM_FLAG_STOP_LATCHED
    safety._stm_flags_at = time.monotonic()
    safety._params = {
        'stale_ms': 300,
        'distance_spread_stop_mm': 30.0,
        'distance_rate_stop_mm_s': 120.0,
        'omega_stop_dps': 120.0,
        'battery_release_mv': 10200,
        'require_distance': True,
    }
    safety._battery_packs_mv = [0, 0]
    safety._battery_flags = 0
    safety._battery_at = None
    safety._battery_monitor_seen = False
    distance = {
        'age_ms': 10, 'valid': [True, True, True], 'spread': 2.0,
        'mean_rate': 0.0, 'calibrated': True,
    }
    assert safety._release_allowed(distance, {'gyro_mag_dps': 0.0})
    safety._stm_flags = 0
    assert not safety._release_allowed(distance, {'gyro_mag_dps': 0.0})
