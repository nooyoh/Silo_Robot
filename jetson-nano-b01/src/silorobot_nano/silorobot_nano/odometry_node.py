#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""Differential-wheel odometry with short-term IMU gyro correction."""

import json
import math
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import Int32MultiArray, String


def normalize_angle(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


class OdometryNode(Node):
    def __init__(self):
        super().__init__('odometry_node')
        # STL bootstrap profile: 85.525 mm estimated drive-sprocket pitch
        # diameter -> 0.2686846 m/rev. Encoder assumption is
        # 16 PPR * 290:1 * x4 = 18,560 counts/output rev.
        # Replace with five-run straight/turn measurements before wall use.
        self.declare_parameter('meters_per_count_left', 0.2686846 / 18560.0)
        self.declare_parameter('meters_per_count_right', 0.2686846 / 18560.0)
        self.declare_parameter('track_width_m', 0.30)
        self.declare_parameter('encoder_alpha', 1.0)
        self.declare_parameter('max_imu_age_ms', 300)
        self.declare_parameter('max_wheel_count_age_ms', 300)
        # A MEMS gyro reads a small nonzero rate while perfectly still, and integrating that
        # bias is what limits gyro-based heading — measured drift stops improving past a few
        # percent of track slip because bias, not slip, dominates it. Average the first
        # samples while the robot is stationary and subtract that from every later reading.
        # Requires the robot to be motionless for this long after the node starts.
        self.declare_parameter('gyro_bias_samples', 200)
        self._left_scale = self.get_parameter('meters_per_count_left').value
        self._right_scale = self.get_parameter('meters_per_count_right').value
        self._track_width = self.get_parameter('track_width_m').value
        self._alpha = self.get_parameter('encoder_alpha').value
        self._max_imu_age_ms = self.get_parameter('max_imu_age_ms').value
        self._max_wheel_count_age_ms = self.get_parameter(
            'max_wheel_count_age_ms').value
        self._bias_target = int(self.get_parameter('gyro_bias_samples').value)
        self._gyro_bias = 0.0
        self._bias_sum = 0.0
        self._bias_count = 0
        self._agree_window = []
        self._publisher = self.create_publisher(String, '/silorobot/pose', 10)
        self.create_subscription(Int32MultiArray, '/silorobot/wheel_counts',
                                 self._on_counts, 10)
        self.create_subscription(Imu, '/silorobot/imu', self._on_imu, 10)
        self._previous_counts = None
        self._previous_count_at = None
        self._gyro_z = None
        self._gyro_at = None
        self._pose = {'x': 0.0, 'y': 0.0, 'theta': 0.0}
        self.create_timer(0.2, self._publish_pose)

    def _calibrated(self):
        # Right can legitimately be negative (mirror-mounted motor, see bootstrap.yaml) —
        # only the magnitude being nonzero means a scale was actually set.
        return self._left_scale != 0 and self._right_scale != 0 and self._track_width > 0

    def _on_imu(self, message):
        raw = float(message.angular_velocity.z)
        if self._bias_count < self._bias_target:
            # Startup window: the robot is assumed stationary, so whatever the gyro reports
            # is bias. Publish nothing but zero rotation until the estimate settles.
            self._bias_sum += raw
            self._bias_count += 1
            self._gyro_bias = self._bias_sum / self._bias_count
            if self._bias_count == self._bias_target:
                self.get_logger().info(
                    'Gyro bias calibrated: {:.5f} rad/s over {} samples'.format(
                        self._gyro_bias, self._bias_count))
        self._gyro_z = raw - self._gyro_bias
        self._gyro_at = time.monotonic()

    def gyro_bias_ready(self):
        return self._bias_count >= self._bias_target

    def _on_counts(self, message):
        if len(message.data) < 2:
            return
        counts = (int(message.data[0]), int(message.data[1]))
        now = time.monotonic()
        if self._previous_counts is None:
            self._previous_counts, self._previous_count_at = counts, now
            return
        previous, previous_at = self._previous_counts, self._previous_count_at
        self._previous_counts, self._previous_count_at = counts, now
        if not self._calibrated() or now <= previous_at:
            return
        dl = (counts[0] - previous[0]) * self._left_scale
        dr = (counts[1] - previous[1]) * self._right_scale
        ds = (dl + dr) / 2.0
        encoder_turn = (dr - dl) / self._track_width
        gyro_turn = None
        # Only trust the gyro once its bias estimate has settled; until then an uncalibrated
        # rate would be integrated straight into heading. Encoders carry it in the meantime.
        if (self._gyro_z is not None and self._gyro_at is not None
                and self.gyro_bias_ready()):
            if (now - self._gyro_at) * 1000 <= self._max_imu_age_ms:
                gyro_turn = self._gyro_z * (now - previous_at)
        alpha = max(0.0, min(1.0, float(self._alpha)))
        if gyro_turn is None:
            turn = encoder_turn
        else:
            self._check_sources_agree(encoder_turn, gyro_turn)
            turn = alpha * encoder_turn + (1.0 - alpha) * gyro_turn
        heading_mid = self._pose['theta'] + turn / 2.0
        self._pose['x'] += ds * math.cos(heading_mid)
        self._pose['y'] += ds * math.sin(heading_mid)
        self._pose['theta'] = normalize_angle(self._pose['theta'] + turn)

    def _check_sources_agree(self, encoder_turn, gyro_turn):
        """Warn when the two heading sources disagree about which way the robot turned.

        Trusting the gyro assumes its Z axis is the robot's yaw axis. A rotated mount, or a
        flipped encoder sign, produces a heading estimate that is confidently wrong in a way
        nothing else surfaces — the robot drives off believing it is on course. Comparing the
        two independent sources catches exactly that, without either having to be correct on
        its own. Only meaningful once turning enough to be above noise.
        """
        self._agree_window.append((encoder_turn, gyro_turn))
        if len(self._agree_window) < 40:
            return
        encoder_total = sum(pair[0] for pair in self._agree_window)
        gyro_total = sum(pair[1] for pair in self._agree_window)
        self._agree_window = []
        if abs(encoder_total) < 0.15 and abs(gyro_total) < 0.15:
            return
        opposed = encoder_total * gyro_total < 0
        scale_off = (max(abs(encoder_total), abs(gyro_total)) >
                     3.0 * max(1e-6, min(abs(encoder_total), abs(gyro_total))))
        if opposed or scale_off:
            self.get_logger().warn(
                'Heading sources disagree over ~2 s: encoder {:+.2f} rad vs gyro {:+.2f} rad. '
                'Check the IMU mounting axis and the encoder sign convention '
                '(ros2 run silorobot_nano verify_signs).'.format(encoder_total, gyro_total))

    def _publish_pose(self):
        wheel_count_age_ms = (
            None if self._previous_count_at is None else
            int((time.monotonic() - self._previous_count_at) * 1000))
        wheel_counts_fresh = (
            wheel_count_age_ms is not None and
            wheel_count_age_ms <= self._max_wheel_count_age_ms)
        gyro_fresh = (
            self._gyro_at is not None and
            (time.monotonic() - self._gyro_at) * 1000 <= self._max_imu_age_ms)
        payload = dict(self._pose)
        payload.update({'conf': 1.0 if self._calibrated() else 0.0,
                        'calibrated': self._calibrated(), 'gyro_fresh': gyro_fresh,
                        'wheel_counts_fresh': wheel_counts_fresh,
                        'wheel_count_age_ms': wheel_count_age_ms,
                        'gyro_bias_ready': self.gyro_bias_ready(),
                        'gyro_bias': round(self._gyro_bias, 6)})
        self._publisher.publish(String(data=json.dumps(payload, allow_nan=False)))


def main(args=None):
    rclpy.init(args=args)
    node = OdometryNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
