#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""WT901C (WIT 11-byte protocol) to ROS2 Imu bridge."""

import json
import math
import time
from collections import deque

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
import serial
from std_msgs.msg import String


WIT_HEADER = 0x55
WIT_FRAME_LENGTH = 11
WIT_TYPES = (0x51, 0x52, 0x53)
GRAVITY = 9.80665


def quaternion_from_euler(roll, pitch, yaw):
    """Return a ZYX quaternion from radians (roll, pitch, yaw)."""
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return (
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )


class WitFrameParser:
    """Streaming parser that survives noise, split reads and bad checksums."""

    def __init__(self):
        self.buffer = bytearray()
        self.frames = 0
        self.checksum_errors = 0

    def feed(self, data):
        self.buffer.extend(data)
        decoded = []
        while True:
            index = self.buffer.find(bytes([WIT_HEADER]))
            if index < 0:
                self.buffer.clear()
                return decoded
            if index:
                del self.buffer[:index]
            if len(self.buffer) < WIT_FRAME_LENGTH:
                return decoded
            frame = self.buffer[:WIT_FRAME_LENGTH]
            if (sum(frame[:10]) & 0xff) != frame[10]:
                self.checksum_errors += 1
                del self.buffer[0]
                continue
            frame_type = frame[1]
            self.frames += 1
            if frame_type in WIT_TYPES:
                values = [int.from_bytes(frame[offset:offset + 2], 'little', signed=True)
                          for offset in range(2, 8, 2)]
                decoded.append((frame_type, values))
            del self.buffer[:WIT_FRAME_LENGTH]


class ImuNode(Node):
    """Read WIT standard frames over FT232 and publish ROS standard units."""

    def __init__(self):
        super().__init__('imu_node')
        self.declare_parameter('port', '/dev/ttyTHS1')
        self.declare_parameter('baud_rate', 9600)
        self.declare_parameter('reconnect_sec', 2.0)
        self.declare_parameter('publish_hz', 20.0)
        self.declare_parameter('stale_ms', 300)
        self.declare_parameter('max_checksum_error_rate', 0.10)
        self._port = self.get_parameter('port').value
        self._baud_rate = self.get_parameter('baud_rate').value
        self._reconnect_sec = self.get_parameter('reconnect_sec').value
        self._stale_ms = self.get_parameter('stale_ms').value
        self._max_error_rate = self.get_parameter('max_checksum_error_rate').value
        publish_hz = self.get_parameter('publish_hz').value

        self._imu_publisher = self.create_publisher(Imu, '/silorobot/imu', 10)
        self._health_publisher = self.create_publisher(
            String, '/silorobot/imu_health', 10)
        self._serial = None
        self._last_connect_attempt = 0.0
        self._parser = WitFrameParser()
        self._samples = {}
        self._last_sample_monotonic = None
        self._last_sample_stamp = None
        self._sample_times = deque(maxlen=200)
        self.create_timer(0.005, self._read_tick)
        self.create_timer(1.0 / max(1.0, publish_hz), self._publish_imu)
        self.create_timer(0.5, self._publish_health)

    def _ensure_serial(self):
        if self._serial is not None and self._serial.is_open:
            return True
        now = time.monotonic()
        if now - self._last_connect_attempt < self._reconnect_sec:
            return False
        self._last_connect_attempt = now
        try:
            self._serial = serial.Serial(
                self._port, self._baud_rate, timeout=0, write_timeout=0.1)
            self._parser = WitFrameParser()
            self._samples.clear()
            self._last_sample_monotonic = None
            self.get_logger().info('Connected to IMU: {} @ {}'.format(
                self._port, self._baud_rate))
            return True
        except (serial.SerialException, OSError) as error:
            self.get_logger().warn('IMU unavailable (retrying): {}'.format(error))
            return False

    def _read_tick(self):
        if not self._ensure_serial():
            return
        try:
            data = self._serial.read_all()
        except serial.SerialException as error:
            self.get_logger().warn('IMU read failed: {}'.format(error))
            self._close_serial()
            return
        for frame_type, raw in self._parser.feed(data):
            if frame_type == 0x51:
                self._samples[frame_type] = [value / 32768.0 * 16.0 for value in raw]
            elif frame_type == 0x52:
                self._samples[frame_type] = [value / 32768.0 * 2000.0 for value in raw]
            elif frame_type == 0x53:
                self._samples[frame_type] = [value / 32768.0 * 180.0 for value in raw]
            self._last_sample_monotonic = time.monotonic()
            self._last_sample_stamp = self.get_clock().now().to_msg()
            self._sample_times.append(self._last_sample_monotonic)

    def _is_valid(self):
        if self._serial is None or not self._serial.is_open:
            return False
        if not all(frame_type in self._samples for frame_type in WIT_TYPES):
            return False
        if self._last_sample_monotonic is None:
            return False
        if self._age_ms() > self._stale_ms:
            return False
        total = self._parser.frames + self._parser.checksum_errors
        return total == 0 or self._parser.checksum_errors / total <= self._max_error_rate

    def _age_ms(self):
        if self._last_sample_monotonic is None:
            return None
        return int((time.monotonic() - self._last_sample_monotonic) * 1000)

    def _publish_imu(self):
        if not self._is_valid():
            return
        accel = self._samples[0x51]
        gyro = self._samples[0x52]
        angles = [math.radians(value) for value in self._samples[0x53]]
        quaternion = quaternion_from_euler(*angles)
        message = Imu()
        message.header.stamp = self._last_sample_stamp
        message.header.frame_id = 'imu_link'
        message.orientation.x, message.orientation.y = quaternion[0], quaternion[1]
        message.orientation.z, message.orientation.w = quaternion[2], quaternion[3]
        message.angular_velocity.x = math.radians(gyro[0])
        message.angular_velocity.y = math.radians(gyro[1])
        message.angular_velocity.z = math.radians(gyro[2])
        message.linear_acceleration.x = accel[0] * GRAVITY
        message.linear_acceleration.y = accel[1] * GRAVITY
        message.linear_acceleration.z = accel[2] * GRAVITY
        message.orientation_covariance[0] = -1.0
        message.angular_velocity_covariance[0] = -1.0
        message.linear_acceleration_covariance[0] = -1.0
        self._imu_publisher.publish(message)

    def _publish_health(self):
        now = time.monotonic()
        while self._sample_times and now - self._sample_times[0] > 5.0:
            self._sample_times.popleft()
        sample_hz = 0.0
        if len(self._sample_times) > 1:
            duration = self._sample_times[-1] - self._sample_times[0]
            if duration > 0:
                sample_hz = (len(self._sample_times) - 1) / duration
        total = self._parser.frames + self._parser.checksum_errors
        rate = self._parser.checksum_errors / total if total else 0.0
        health = {
            'connected': bool(self._serial and self._serial.is_open),
            'port': self._port, 'sample_hz': round(sample_hz, 2),
            'checksum_error_rate': round(rate, 6),
            'last_sample_age_ms': self._age_ms(), 'valid': self._is_valid(),
            'types_seen': ['0x{:02x}'.format(key) for key in sorted(self._samples)],
        }
        self._health_publisher.publish(String(data=json.dumps(health, allow_nan=False)))

    def _close_serial(self):
        if self._serial is not None:
            try:
                self._serial.close()
            except serial.SerialException:
                pass
        self._serial = None

    def destroy_node(self):
        self._close_serial()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ImuNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
