#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""Settle the odometry/steering sign conventions empirically, in about ten seconds.

Two signs have to agree for autonomous following to converge at all, and getting
either backwards looks identical from the outside (the robot turns forever without
approaching the target):

  * the encoder scale sign  — must make pose x/y advance when driving FORWARD
  * the turn command sign   — path_follower assumes turn > 0 makes theta DECREASE

This node only listens. Drive the robot manually from the dashboard while it runs:
push THROTTLE forward briefly, then push STEERING right briefly. It correlates the
commands it saw with the pose change that followed and prints a verdict for each.

    ros2 run silorobot_nano verify_signs
"""

import json
import math

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


# Ignore the near-zero dither around a released stick; only judge deliberate pushes.
COMMAND_THRESHOLD = 5.0
# A verdict needs enough accumulated motion that encoder noise cannot flip its sign.
FORWARD_CONFIDENT_M = 0.05
TURN_CONFIDENT_RAD = 0.20


def normalize_angle(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


class SignVerifier(Node):
    def __init__(self):
        super().__init__('verify_signs')
        self._command = None
        self._pose = None
        # Signed totals: command direction multiplied by the motion it produced.
        self._forward_agreement = 0.0
        self._turn_agreement = 0.0
        self._forward_seen = 0.0
        self._turn_seen = 0.0
        self.create_subscription(
            Twist, '/silorobot/drive_command', self._on_command, 10)
        self.create_subscription(String, '/silorobot/pose', self._on_pose, 10)
        self.create_timer(1.0, self._report)
        print(__doc__)
        print('대시보드로 (1) 전진을 잠깐, (2) 우회전을 잠깐 밀어보세요. Ctrl+C로 종료.\n')

    def _on_command(self, message):
        self._command = (float(message.linear.x), float(message.angular.z))

    def _on_pose(self, message):
        try:
            pose = json.loads(message.data)
            x, y = float(pose['x']), float(pose['y'])
            theta = float(pose['theta'])
        except (TypeError, ValueError, KeyError):
            return
        previous, self._pose = self._pose, (x, y, theta)
        if previous is None or self._command is None:
            return

        throttle, turn = self._command
        px, py, ptheta = previous
        # Project the step onto the heading we were facing, so backing up reads negative
        # instead of just "some distance moved".
        forward = (x - px) * math.cos(ptheta) + (y - py) * math.sin(ptheta)
        turned = normalize_angle(theta - ptheta)

        if abs(throttle) > COMMAND_THRESHOLD and abs(turn) <= COMMAND_THRESHOLD:
            self._forward_agreement += math.copysign(forward, throttle)
            self._forward_seen += abs(forward)
        elif abs(turn) > COMMAND_THRESHOLD and abs(throttle) <= COMMAND_THRESHOLD:
            # path_follower's convention: a positive turn command must lower theta.
            self._turn_agreement += math.copysign(-turned, turn)
            self._turn_seen += abs(turned)

    @staticmethod
    def _verdict(agreement, seen, confident, ok_text, bad_text):
        if seen < confident:
            return '  [대기] 아직 데이터 부족 (누적 {:.3f})'.format(seen)
        return '  [{}] {}'.format('정상', ok_text) if agreement > 0 else \
               '  [뒤집힘] {}'.format(bad_text)

    def _report(self):
        print('전진 부호:')
        print(self._verdict(
            self._forward_agreement, self._forward_seen, FORWARD_CONFIDENT_M,
            'meters_per_count 부호 정상 (전진 명령 -> pose 전진)',
            'meters_per_count_left/right 부호를 **둘 다 함께** 반대로 바꾸세요'))
        print('조향 부호:')
        print(self._verdict(
            self._turn_agreement, self._turn_seen, TURN_CONFIDENT_RAD,
            'path_follower 조향 부호 정상 (turn>0 -> theta 감소)',
            'path_follower의 turn 계산 앞 마이너스를 빼세요(부호 반대)'))
        print('')


def main(args=None):
    rclpy.init(args=args)
    node = SignVerifier()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
