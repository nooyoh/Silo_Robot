#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""Low-speed waypoint follower; manual mode is the safe default."""

import json
import math
import time

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def normalize_angle(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


class PathFollower(Node):
    """Publish drive commands only while explicitly in AUTO/RUNNING mode."""

    def __init__(self):
        super().__init__('path_follower')
        self.declare_parameter('control_hz', 20.0)
        self.declare_parameter('waypoint_radius_m', 0.05)
        self.declare_parameter('heading_gain', 1.0)
        self.declare_parameter('align_threshold_deg', 20.0)
        self.declare_parameter('heading_deadband_deg', 5.0)
        self.declare_parameter('max_throttle', 15.0)
        self.declare_parameter('max_turn', 20.0)
        # Distance-proportional slowdown near a waypoint (throttle) and heading_gain*error
        # (turn) both taper toward zero with no floor, so both eventually command a value
        # below the drivetrain's deadzone (~20% measured UNLOADED on 2026-08-18 — assembled
        # and loaded is very likely higher, hence 30 not 20 here) while the code still thinks
        # it is moving/turning. The robot then silently stalls: short of waypoint_radius_m for
        # throttle, partway through aligning for turn. Floor both whenever nonzero is intended.
        self.declare_parameter('min_effective_throttle', 30.0)
        self.declare_parameter('min_effective_turn', 30.0)
        self.declare_parameter('pose_timeout_ms', 500)
        self.declare_parameter('safety_timeout_ms', 500)
        self.declare_parameter('progress_timeout_sec', 4.0)
        self.declare_parameter('min_progress_m', 0.005)
        self.declare_parameter('min_progress_deg', 2.0)
        # Normal field operation requires safety monitoring to be armed.  An explicit
        # launch override exists for restrained HIL/bench tests without distance sensors.
        self.declare_parameter('allow_unarmed_autonomy', False)
        self._radius = self.get_parameter('waypoint_radius_m').value
        self._heading_gain = self.get_parameter('heading_gain').value
        self._align_threshold = math.radians(
            self.get_parameter('align_threshold_deg').value)
        self._heading_deadband = math.radians(
            self.get_parameter('heading_deadband_deg').value)
        self._max_throttle = self.get_parameter('max_throttle').value
        self._max_turn = self.get_parameter('max_turn').value
        # Never let the floor exceed the ceiling — a config with a low max_throttle/max_turn
        # (e.g. the conservative 15/20 defaults) must not end up commanding more than its own
        # max just to clear the deadzone floor.
        self._min_effective_throttle = min(
            self.get_parameter('min_effective_throttle').value, self._max_throttle)
        self._min_effective_turn = min(
            self.get_parameter('min_effective_turn').value, self._max_turn)
        self._pose_timeout_ms = self.get_parameter('pose_timeout_ms').value
        self._safety_timeout_ms = self.get_parameter('safety_timeout_ms').value
        self._progress_timeout = self.get_parameter('progress_timeout_sec').value
        self._min_progress_m = self.get_parameter('min_progress_m').value
        self._min_progress_rad = math.radians(
            self.get_parameter('min_progress_deg').value)
        self._allow_unarmed_autonomy = bool(
            self.get_parameter('allow_unarmed_autonomy').value)
        self._drive_publisher = self.create_publisher(Twist, '/silorobot/drive_command', 10)
        self._state_publisher = self.create_publisher(String, '/silorobot/mission_state', 10)
        self.create_subscription(String, '/silorobot/pose', self._on_pose, 10)
        self.create_subscription(String, '/silorobot/plan', self._on_plan, 10)
        self.create_subscription(String, '/silorobot/safety_state', self._on_safety, 10)
        self.create_subscription(String, '/silorobot/autonomy_command', self._on_command, 10)
        self._mode = 'MANUAL'
        self._state = 'IDLE'
        self._plan = None
        self._pose = None
        self._pose_at = None
        self._waypoint_index = 0
        self._safety_state = 'OFFLINE'
        self._safety_armed = False
        self._safety_at = None
        self._last_debug_log = 0.0
        self._anchor = None
        self._progress_pose = None
        self._progress_at = None
        self.create_timer(1.0 / max(1.0, self.get_parameter('control_hz').value), self._tick)

    def _on_pose(self, message):
        try:
            pose = json.loads(message.data)
            if all(math.isfinite(float(pose[key])) for key in ('x', 'y', 'theta')):
                self._pose = pose
                self._pose_at = time.monotonic()
        except (TypeError, ValueError, KeyError):
            return

    def _on_plan(self, message):
        try:
            plan = json.loads(message.data)
            if not isinstance(plan.get('waypoints'), list) or not plan['waypoints']:
                raise ValueError('empty waypoints')
        except (TypeError, ValueError, KeyError) as error:
            self.get_logger().warn('Rejected plan: {}'.format(error))
            return
        if self._state == 'RUNNING':
            self._publish_zero()
        self._mode = 'MANUAL'
        self._plan, self._waypoint_index = plan, 0
        self._anchor = None
        self._state = 'READY'

    def _set_anchor(self):
        """Pin the plan's first waypoint to wherever the robot is standing right now.

        coverage_planner emits waypoints in silo coordinates whose origin is the
        bottom-left corner, but odometry always starts at (0, 0, 0) wherever the robot
        happened to be powered up — the two frames were never tied together. With the
        default TOP_LEFT start corner that means the robot, physically placed at the top
        left, believes it is at the bottom left and drives off toward a corner it is
        already standing on. Anchoring makes "place the robot at the start corner facing
        along the first leg, then press start" behave the way the operator expects.
        """
        waypoints = (self._plan or {}).get('waypoints') or []
        if self._pose is None or not waypoints:
            return False
        first = waypoints[0]
        plan_heading = 0.0
        if len(waypoints) > 1:
            plan_heading = math.atan2(float(waypoints[1]['y']) - float(first['y']),
                                      float(waypoints[1]['x']) - float(first['x']))
        self._anchor = {
            'px': float(first['x']), 'py': float(first['y']),
            'x': float(self._pose['x']), 'y': float(self._pose['y']),
            'th': normalize_angle(float(self._pose['theta']) - plan_heading),
        }
        return True

    def _to_odom(self, waypoint):
        """Plan-frame waypoint -> odometry frame, using the start-time anchor."""
        anchor = self._anchor
        px, py = float(waypoint['x']), float(waypoint['y'])
        if anchor is None:
            return px, py
        dx, dy = px - anchor['px'], py - anchor['py']
        cos_t, sin_t = math.cos(anchor['th']), math.sin(anchor['th'])
        return (anchor['x'] + cos_t * dx - sin_t * dy,
                anchor['y'] + sin_t * dx + cos_t * dy)

    def _to_plan(self, x, y, theta):
        """Odometry pose -> plan frame, so the dashboard can draw it on the plan diagram."""
        anchor = self._anchor
        if anchor is None:
            return x, y, theta
        dx, dy = x - anchor['x'], y - anchor['y']
        cos_t, sin_t = math.cos(anchor['th']), math.sin(anchor['th'])
        return (anchor['px'] + cos_t * dx + sin_t * dy,
                anchor['py'] - sin_t * dx + cos_t * dy,
                normalize_angle(theta - anchor['th']))

    def _on_safety(self, message):
        try:
            payload = json.loads(message.data)
            if not isinstance(payload, dict):
                return
            state = payload.get('state', 'OFFLINE')
        except (TypeError, ValueError):
            return
        self._safety_state = state
        self._safety_armed = bool(payload.get('armed', False))
        self._safety_at = time.monotonic()
        if state != 'NORMAL' and self._state == 'RUNNING':
            self._state = 'PAUSED_SAFETY'
            self._publish_zero()

    @staticmethod
    def _fresh(timestamp, timeout_ms):
        return (timestamp is not None and
                (time.monotonic() - timestamp) * 1000 <= timeout_ms)

    def _pose_ready(self):
        if self._pose is None or not self._fresh(self._pose_at, self._pose_timeout_ms):
            return False
        if not bool(self._pose.get('calibrated', False)):
            return False
        # Older pose producers omit this key; retain rolling-upgrade compatibility.  The
        # shipped odometry node now publishes it explicitly, so stopped encoder telemetry is
        # rejected within 300 ms while the progress watchdog covers a live-but-frozen count.
        return bool(self._pose.get('wheel_counts_fresh', True))

    def _safety_ready(self):
        if not self._fresh(self._safety_at, self._safety_timeout_ms):
            return False
        if self._safety_state != 'NORMAL':
            return False
        return self._safety_armed or self._allow_unarmed_autonomy

    def _autonomy_ready(self):
        return self._pose_ready() and self._safety_ready()

    def _reset_progress_watch(self):
        if self._pose is None:
            self._progress_pose = None
            self._progress_at = None
            return
        self._progress_pose = (
            float(self._pose['x']), float(self._pose['y']), float(self._pose['theta']))
        self._progress_at = time.monotonic()

    def _progress_is_live(self):
        """Require either translation or rotation while nonzero drive is commanded."""
        if self._progress_pose is None or self._progress_at is None:
            self._reset_progress_watch()
            return True
        x, y, theta = self._progress_pose
        moved = math.hypot(float(self._pose['x']) - x, float(self._pose['y']) - y)
        turned = abs(normalize_angle(float(self._pose['theta']) - theta))
        if moved >= self._min_progress_m or turned >= self._min_progress_rad:
            self._reset_progress_watch()
            return True
        return time.monotonic() - self._progress_at <= self._progress_timeout

    def _on_command(self, message):
        try:
            command = json.loads(message.data)
        except (TypeError, ValueError):
            return
        command_type = command.get('type')
        if command_type == 'route_start' and self._plan and self._autonomy_ready():
            # Anchor before running: without a pose we cannot tie the plan frame to the
            # robot, and starting anyway would drive toward raw plan coordinates.
            if not self._set_anchor():
                self.get_logger().warn('route_start ignored: no pose yet, cannot anchor plan')
                return
            self._waypoint_index = 0
            self._mode, self._state = 'AUTO', 'RUNNING'
            self._reset_progress_watch()
        elif command_type == 'route_pause' and self._state == 'RUNNING':
            self._state = 'PAUSED_USER'
            self._publish_zero()
        elif (command_type == 'route_resume' and
              self._state in ('READY', 'PAUSED_USER', 'PAUSED_SAFETY',
                              'RECOVERY_REQUIRED') and self._autonomy_ready()):
            if self._anchor is None and not self._set_anchor():
                return
            self._mode, self._state = 'AUTO', 'RUNNING'
            self._reset_progress_watch()
        elif command_type == 'route_cancel':
            self._mode, self._state, self._plan = 'MANUAL', 'IDLE', None
            self._anchor = None
            self._progress_pose = None
            self._progress_at = None
            self._publish_zero()

    def _tick(self):
        if self._state == 'RUNNING':
            if not self._safety_ready():
                self._state = 'PAUSED_SAFETY'
                self._publish_zero()
            elif not self._pose_ready():
                self._state = 'RECOVERY_REQUIRED'
                self._publish_zero()
        # This is the single-publisher mode rule: while manual or paused this
        # node emits no drive topic at all, so dashboard_bridge owns it.
        if self._mode == 'AUTO' and self._state == 'RUNNING':
            self._follow_once()
        self._publish_state()

    def _follow_once(self):
        if self._pose is None or self._plan is None:
            self._state = 'RECOVERY_REQUIRED'
            self._publish_zero()
            return
        waypoints = self._plan['waypoints']
        if self._waypoint_index >= len(waypoints):
            self._state, self._mode = 'COMPLETE', 'MANUAL'
            self._publish_zero()
            return
        target_x, target_y = self._to_odom(waypoints[self._waypoint_index])
        dx = target_x - float(self._pose['x'])
        dy = target_y - float(self._pose['y'])
        distance = math.hypot(dx, dy)
        if distance <= self._radius:
            self._publish_zero()
            self._waypoint_index += 1
            self._reset_progress_watch()
            if self._waypoint_index >= len(waypoints):
                self._state, self._mode = 'COMPLETE', 'MANUAL'
            return
        wanted = math.atan2(dy, dx)
        heading_error = normalize_angle(wanted - float(self._pose['theta']))
        now = time.monotonic()
        if now - self._last_debug_log >= 1.0:
            self._last_debug_log = now
            self.get_logger().info(
                'wp{} target=({:.2f},{:.2f}) pose=({:.2f},{:.2f},{:.1f}deg) '
                'dist={:.2f}m heading_err={:.1f}deg'.format(
                    self._waypoint_index, target_x, target_y,
                    self._pose['x'], self._pose['y'],
                    math.degrees(float(self._pose['theta'])),
                    distance, math.degrees(heading_error)))
        drive = Twist()
        # First align in place. Driving through a large heading error rounds a
        # lane-end corner and can leave the planner's safety margin.
        if abs(heading_error) <= self._align_threshold:
            heading_scale = max(0.0, math.cos(heading_error))
            wanted_throttle = min(
                self._max_throttle,
                max(0.0, distance * self._max_throttle * heading_scale))
            # Below the drivetrain's deadzone the wheels do not turn at all, so a naive
            # distance-proportional slowdown stalls short of waypoint_radius_m every time —
            # floor it at the minimum effective value whenever we still intend to move.
            if 0.0 < wanted_throttle < self._min_effective_throttle:
                wanted_throttle = self._min_effective_throttle
            drive.linear.x = wanted_throttle
        else:
            drive.linear.x = 0.0
        # Small heading noise (encoder jitter) otherwise keeps flipping turn's sign every tick,
        # which shows up as one track chattering forward/backward while the other stays steady
        # (throttle absorbs the jitter, the smaller track's throttle-minus-turn does not).
        if abs(heading_error) <= self._heading_deadband:
            turn = 0.0
        else:
            # NOTE THE MINUS. The drive chain's turn axis is clockwise-positive, not the
            # ROS/CCW-positive convention this formula was written for: STM32 mixes
            # left = throttle + turn / right = throttle - turn, so turn > 0 speeds up the
            # left track and swings the robot RIGHT, which DECREASES theta. Commanding a
            # positive turn for a positive heading_error therefore steered away from the
            # target and the error grew without bound — the robot span forever instead of
            # converging. Negate so a positive heading error produces a left turn.
            turn = -self._heading_gain * heading_error * self._max_turn / math.pi
            # Same deadzone problem as throttle above, worse here: heading_gain*max_turn/pi
            # means most of the align_threshold range produces a |turn| below the deadzone,
            # so the correction is computed but never physically happens — the robot stalls
            # partway through aligning instead of finishing the turn.
            if 0.0 < abs(turn) < self._min_effective_turn:
                turn = math.copysign(self._min_effective_turn, turn)
        drive.angular.z = max(-self._max_turn, min(self._max_turn, turn))
        if ((abs(drive.linear.x) > 0.0 or abs(drive.angular.z) > 0.0)
                and not self._progress_is_live()):
            self.get_logger().error(
                'Autonomy stopped: no encoder-derived pose progress for {:.1f}s'.format(
                    self._progress_timeout))
            self._state = 'RECOVERY_REQUIRED'
            self._publish_zero()
            return
        self._drive_publisher.publish(drive)

    def _publish_zero(self):
        """Immediately stop at a user mode transition; do not wait for timeout."""
        self._drive_publisher.publish(Twist())

    def _publish_state(self):
        total = len(self._plan.get('waypoints', [])) if self._plan else 0
        payload = {
            'mode': self._mode, 'state': self._state,
            'plan_id': self._plan.get('plan_id') if self._plan else None,
            'current_waypoint': self._waypoint_index, 'total_waypoints': total,
            'coverage_ratio': self._waypoint_index / total if total else 0.0,
            'input_health': {
                'pose_fresh': self._pose_ready(),
                'safety_fresh': self._fresh(self._safety_at, self._safety_timeout_ms),
                'safety_armed': self._safety_armed,
                'bench_override': self._allow_unarmed_autonomy,
            },
        }
        # The dashboard draws the plan in plan coordinates, so hand it the live pose
        # already converted into that frame — otherwise the marker sits wherever odometry's
        # arbitrary power-on origin happens to be rather than on the drawn route.
        if self._pose is not None and self._anchor is not None:
            plan_x, plan_y, plan_theta = self._to_plan(
                float(self._pose['x']), float(self._pose['y']), float(self._pose['theta']))
            payload['plan_pose'] = {'x': plan_x, 'y': plan_y, 'theta': plan_theta}
        self._state_publisher.publish(String(data=json.dumps(payload, allow_nan=False)))


def main(args=None):
    rclpy.init(args=args)
    node = PathFollower()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
