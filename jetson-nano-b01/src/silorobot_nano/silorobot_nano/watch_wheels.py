#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""Live left/right wheel-count delta printer for encoder direction checks.

Run this directly at the Nano's own terminal (not over a coordinated SSH
capture window) so there is no timing mismatch between "start recording" and
"push the stick" — the first sample becomes the baseline and every following
line shows the running delta against it. Ctrl+C to stop.
"""

import sys

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32MultiArray


class WheelWatcher(Node):
    def __init__(self):
        super().__init__('watch_wheels')
        self._baseline = None
        self.create_subscription(
            Int32MultiArray, '/silorobot/wheel_counts', self._on_counts, 20)

    def _on_counts(self, message):
        if len(message.data) < 2:
            return
        left, right = int(message.data[0]), int(message.data[1])
        if self._baseline is None:
            self._baseline = (left, right)
            print('baseline: left={} right={}'.format(left, right))
            return
        base_left, base_right = self._baseline
        print('delta: left={:+d} right={:+d}'.format(
            left - base_left, right - base_right))
        sys.stdout.flush()


def main(args=None):
    rclpy.init(args=args)
    node = WheelWatcher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
