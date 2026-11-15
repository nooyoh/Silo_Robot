#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""Collect synchronized bring-up telemetry into an append-only CSV file."""

import argparse
import csv
import pathlib
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import Int32MultiArray, UInt16MultiArray


FIELDS = [
    'time_s', 'target_mm', 'adc_1', 'adc_2', 'adc_3',
    'left_count', 'right_count', 'gyro_z_rad_s',
]


class CalibrationCollector(Node):
    def __init__(self, output, target_mm):
        super().__init__('calibration_collector')
        self._output = pathlib.Path(output).expanduser()
        self._target_mm = target_mm
        self._counts = [None, None]
        self._gyro_z = None
        self._rows = 0
        self._output.parent.mkdir(parents=True, exist_ok=True)
        new_file = not self._output.exists() or self._output.stat().st_size == 0
        self._stream = self._output.open('a', newline='', encoding='utf-8')
        self._writer = csv.DictWriter(self._stream, fieldnames=FIELDS)
        if new_file:
            self._writer.writeheader()
        self.create_subscription(UInt16MultiArray, '/silorobot/distance_adc', self._on_adc, 20)
        self.create_subscription(Int32MultiArray, '/silorobot/wheel_counts', self._on_counts, 20)
        self.create_subscription(Imu, '/silorobot/imu', self._on_imu, 20)

    @property
    def rows(self):
        return self._rows

    def _on_counts(self, message):
        if len(message.data) >= 2:
            self._counts = [int(message.data[0]), int(message.data[1])]

    def _on_imu(self, message):
        self._gyro_z = float(message.angular_velocity.z)

    def _on_adc(self, message):
        if len(message.data) < 3:
            return
        self._writer.writerow({
            'time_s': '{:.6f}'.format(time.time()),
            'target_mm': '' if self._target_mm is None else self._target_mm,
            'adc_1': int(message.data[0]),
            'adc_2': int(message.data[1]),
            'adc_3': int(message.data[2]),
            'left_count': '' if self._counts[0] is None else self._counts[0],
            'right_count': '' if self._counts[1] is None else self._counts[1],
            'gyro_z_rad_s': '' if self._gyro_z is None else '{:.8f}'.format(self._gyro_z),
        })
        self._stream.flush()
        self._rows += 1

    def close(self):
        self._stream.close()


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='calibration/silorobot.csv')
    parser.add_argument('--duration', type=float, default=5.0)
    parser.add_argument('--target-mm', type=int)
    return parser


def main(args=None):
    parsed = build_parser().parse_args(args)
    if parsed.duration <= 0 or (parsed.target_mm is not None and parsed.target_mm <= 0):
        raise SystemExit('duration and target-mm must be positive')
    rclpy.init()
    node = CalibrationCollector(parsed.output, parsed.target_mm)
    deadline = time.monotonic() + parsed.duration
    try:
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()
    print('saved {} rows to {}'.format(node.rows, pathlib.Path(parsed.output).resolve()))
    if node.rows == 0:
        raise SystemExit('no distance_adc samples received')


if __name__ == '__main__':
    main()
