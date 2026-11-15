#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""Open-loop 0.5 x 0.5 m planner-screen demo for time-critical filming.

This publishes the normal plan/mission schema so the dashboard route, marker
and progress move with the motor timeline. Physical movement is open loop and
the displayed scale is not encoder-measured distance. Dashboard emergency stop
and the STM32 command timeout stay in the command path.
"""

import json
import math
import time

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String


def make_square_segments(side_seconds, turn_seconds, settle_seconds,
                         straight_command, turn_command):
    """Return four straight legs and four right turns with settling gaps."""
    segments = []
    for leg in range(4):
        segments.append(('side-{}'.format(leg + 1), side_seconds,
                         straight_command, 0.0))
        segments.append(('settle', settle_seconds, 0.0, 0.0))
        segments.append(('turn-{}'.format(leg + 1), turn_seconds,
                         0.0, turn_command))
        segments.append(('settle', settle_seconds, 0.0, 0.0))
    return segments


def make_demo_plan(size_m=0.5, plan_id='DEMO-0P5M-SQUARE'):
    """Return a clockwise square in the dashboard's normal route-plan schema."""
    size = max(0.1, float(size_m))
    waypoints = [
        {'x': 0.0, 'y': size}, {'x': size, 'y': size},
        {'x': size, 'y': 0.0}, {'x': 0.0, 'y': 0.0},
        {'x': 0.0, 'y': size},
    ]
    return {
        'type': 'route_plan', 'plan_id': plan_id,
        'planner': 'DEMO_SQUARE_TIMELINE_V1', 'surface': 'RECTANGLE',
        'width_m': size, 'height_m': size, 'scan_width_m': size,
        'overlap_ratio': 0.0, 'safety_margin_m': 0.0,
        'start_corner': 'TOP_LEFT', 'orientation': 'HORIZONTAL',
        'estimated_length_m': round(4.0 * size, 4),
        'estimated_cost': round(4.0 * size, 4), 'turn_count': 4,
        'waypoints': waypoints,
        'candidates': [{
            'orientation': 'HORIZONTAL',
            'estimated_length_m': round(4.0 * size, 4),
            'turn_count': 4, 'estimated_cost': round(4.0 * size, 4),
        }],
    }


class DemoSquare(Node):
    """Publish a guarded, time-based square sequence at the STM32 command rate."""

    def __init__(self):
        super().__init__('demo_square')
        self.declare_parameter('control_hz', 20.0)
        self.declare_parameter('start_delay_sec', 5.0)
        self.declare_parameter('release_timeout_sec', 8.0)
        self.declare_parameter('square_size_m', 0.5)
        # 4*1.5 + 4*0.6 + 8*0.2 = 10.0 seconds of visible execution.
        self.declare_parameter('side_seconds', 1.5)
        self.declare_parameter('turn_seconds', 0.6)
        self.declare_parameter('settle_seconds', 0.2)
        self.declare_parameter('straight_command', 50.0)
        # Positive turn is clockwise/right in the shipped arcade-mix convention.
        self.declare_parameter('turn_command', 40.0)

        self._control_hz = max(5.0, float(self.get_parameter('control_hz').value))
        self._start_delay = max(
            1.0, float(self.get_parameter('start_delay_sec').value))
        self._release_timeout = max(
            self._start_delay,
            float(self.get_parameter('release_timeout_sec').value))
        self._segments = make_square_segments(
            max(0.1, float(self.get_parameter('side_seconds').value)),
            max(0.1, float(self.get_parameter('turn_seconds').value)),
            max(0.0, float(self.get_parameter('settle_seconds').value)),
            self._axis('straight_command'), self._axis('turn_command'))
        self._plan = make_demo_plan(
            float(self.get_parameter('square_size_m').value))
        self._headings = [0.0, -math.pi / 2.0, math.pi, math.pi / 2.0]

        self._drive_publisher = self.create_publisher(
            Twist, '/silorobot/drive_command', 10)
        self._release_publisher = self.create_publisher(
            Bool, '/silorobot/stop_request', 10)
        self._plan_publisher = self.create_publisher(
            String, '/silorobot/plan', 10)
        self._state_publisher = self.create_publisher(
            String, '/silorobot/mission_state', 10)
        self.create_subscription(
            Bool, '/silorobot/emergency_stop', self._on_emergency_stop, 10)

        now = time.monotonic()
        self._created_at = now
        self._released_at = None
        self._segment_started_at = None
        self._segment_index = 0
        self._release_seen = False
        self._aborted = False
        self._complete = False
        self._last_release_request = 0.0
        self._last_plan_publish = 0.0
        self.create_timer(1.0 / self._control_hz, self._tick)
        self.get_logger().warn(
            '10 S PLANNER-SCREEN DEMO: 0.5 m display; open-loop physical motion')

    def _axis(self, parameter):
        return max(-100.0, min(100.0, float(self.get_parameter(parameter).value)))

    def _on_emergency_stop(self, message):
        if not bool(message.data):
            if not self._release_seen:
                self._release_seen = True
                self._released_at = time.monotonic()
                self.get_logger().info(
                    'Stop latch released; square starts in {:.1f}s'.format(
                        self._start_delay))
            return
        # The supervisor boots latched, so an initial True is expected. Once a
        # release has been observed, any new True is an operator/safety stop and
        # must abort permanently; never auto-release an in-run emergency stop.
        if self._release_seen and not self._complete:
            self._abort('dashboard or safety emergency stop')

    def _publish_drive(self, throttle=0.0, turn=0.0):
        message = Twist()
        message.linear.x = float(throttle)
        message.angular.z = float(turn)
        self._drive_publisher.publish(message)

    @staticmethod
    def _lerp(a, b, ratio):
        return float(a) + (float(b) - float(a)) * max(0.0, min(1.0, ratio))

    def _timeline_state(self, now):
        """Build dashboard mission state synchronized with the motor timeline."""
        waypoints = self._plan['waypoints']
        current = 0
        pose = dict(waypoints[0], theta=self._headings[0])
        mode, state = 'AUTO', 'READY'
        if self._aborted:
            return 'MANUAL', 'ABORTED', current, pose
        if self._complete:
            return 'MANUAL', 'COMPLETE', len(waypoints), dict(
                waypoints[-1], theta=self._headings[0])
        if self._segment_index >= len(self._segments):
            return 'AUTO', 'RUNNING', len(waypoints) - 1, dict(
                waypoints[-1], theta=self._headings[0])
        if (not self._release_seen or
                now - self._released_at < self._start_delay):
            return mode, state, current, pose

        state = 'RUNNING'
        cycle = min(3, self._segment_index // 4)
        phase = self._segment_index % 4
        start = waypoints[cycle]
        end = waypoints[cycle + 1]
        current = cycle
        elapsed = 0.0 if self._segment_started_at is None else (
            now - self._segment_started_at)
        duration = self._segments[self._segment_index][1]
        ratio = 1.0 if duration <= 0.0 else min(1.0, elapsed / duration)
        heading = self._headings[cycle]
        if phase == 0:
            pose = {
                'x': self._lerp(start['x'], end['x'], ratio),
                'y': self._lerp(start['y'], end['y'], ratio),
                'theta': heading,
            }
        elif phase == 1:
            current = cycle + 1
            pose = dict(end, theta=heading)
        elif phase == 2:
            current = cycle + 1
            next_heading = self._headings[(cycle + 1) % 4]
            delta = math.atan2(
                math.sin(next_heading - heading), math.cos(next_heading - heading))
            pose = dict(end, theta=heading + delta * ratio)
        else:
            current = cycle + 1
            pose = dict(end, theta=self._headings[(cycle + 1) % 4])
        return mode, state, current, pose

    def _publish_dashboard(self, now):
        if now - self._last_plan_publish >= 1.0:
            self._last_plan_publish = now
            self._plan_publisher.publish(String(
                data=json.dumps(self._plan, allow_nan=False)))
        mode, state, current, pose = self._timeline_state(now)
        total = len(self._plan['waypoints'])
        payload = {
            'mode': mode, 'state': state, 'plan_id': self._plan['plan_id'],
            'current_waypoint': current, 'total_waypoints': total,
            'coverage_ratio': min(1.0, current / max(1, total - 1)),
            'plan_pose': pose,
            'demo': True, 'display_size_m': self._plan['width_m'],
        }
        self._state_publisher.publish(String(
            data=json.dumps(payload, allow_nan=False)))

    def _abort(self, reason):
        if self._aborted:
            return
        self._aborted = True
        self._publish_drive()
        self.get_logger().error('demo-square aborted: {}'.format(reason))

    def _tick(self):
        now = time.monotonic()
        self._publish_dashboard(now)
        if self._aborted or self._complete:
            self._publish_drive()
            return

        if not self._release_seen:
            self._publish_drive()
            # Request release only during startup. Repeating briefly survives DDS
            # discovery without creating an automatic re-arm path after an E-stop.
            if now - self._last_release_request >= 0.2:
                self._last_release_request = now
                self._release_publisher.publish(Bool(data=False))
            if now - self._created_at > self._release_timeout:
                self._abort('stop latch did not release before timeout')
            return

        if now - self._released_at < self._start_delay:
            self._publish_drive()
            return

        if self._segment_index >= len(self._segments):
            self._complete = True
            self._publish_drive()
            self.get_logger().info('demo-square complete; motors stopped')
            return

        if self._segment_started_at is None:
            self._segment_started_at = now
            name = self._segments[self._segment_index][0]
            self.get_logger().info(
                'segment {}/{}: {}'.format(
                    self._segment_index + 1, len(self._segments), name))

        name, duration, throttle, turn = self._segments[self._segment_index]
        if now - self._segment_started_at >= duration:
            self._publish_drive()
            self._segment_index += 1
            self._segment_started_at = None
            return
        self._publish_drive(throttle, turn)

    def stop(self):
        """Best-effort explicit zero; STM32 also stops after 300 ms on loss."""
        self._publish_drive()


def main(args=None):
    rclpy.init(args=args)
    node = DemoSquare()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
