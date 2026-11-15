#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""Live gyro Z sign check — same idea as watch_wheels but for the IMU.

Run at the Nano's own terminal while pushing the dashboard steering one way.
Positive turn command (우회전) should show a consistent-sign gyro_z here;
compare against odometry_node's turn convention (positive turn -> theta
increases, confirmed 2026-08-21 via watch_wheels) before trusting
encoder_alpha=0 (pure-gyro turn estimate).
"""

import math

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu


class GyroWatcher(Node):
    def __init__(self):
        super().__init__('watch_gyro')
        self.create_subscription(Imu, '/silorobot/imu', self._on_imu, 20)

    def _on_imu(self, message):
        gz_dps = math.degrees(message.angular_velocity.z)
        print('gyro_z = {:+7.2f} deg/s'.format(gz_dps))


def main(args=None):
    rclpy.init(args=args)
    node = GyroWatcher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
