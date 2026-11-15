#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""STM32 ST-LINK VCP bridge for SiloRobot drive and distance telemetry."""

import time

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
import serial
from std_msgs.msg import Bool, Float32, Int32MultiArray, UInt16MultiArray, UInt8
from std_msgs.msg import UInt8MultiArray


FRAME_START = 0xAA
FRAME_END = 0x55
TELEMETRY_START = 0xBB
ENCODER_START = 0xBC
ADC_START = 0xBD
BATTERY_START = 0xBE
CMD_MOVE = 0x01
CMD_STOP = 0x02
CMD_STOP_RELEASE = 0x03


class Stm32UartBridge(Node):
    """Relay drive commands and STM32 telemetry over the ST-LINK VCP UART."""

    def __init__(self):
        super().__init__('stm32_uart_bridge')

        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('command_hz', 20.0)
        self.declare_parameter('drive_timeout_sec', 0.3)
        self.declare_parameter('reconnect_sec', 2.0)

        self._port = self.get_parameter('port').value
        self._baud_rate = self.get_parameter('baud_rate').value
        self._command_hz = self.get_parameter('command_hz').value
        self._drive_timeout = self.get_parameter('drive_timeout_sec').value
        self._reconnect_sec = self.get_parameter('reconnect_sec').value

        self._distance_publisher = self.create_publisher(
            UInt8MultiArray, '/silorobot/distances_mm', 10)
        self._flags_publisher = self.create_publisher(
            UInt8, '/silorobot/stm32_flags', 10)
        self._connected_publisher = self.create_publisher(
            Bool, '/silorobot/stm32_connected', 10)
        self._wheel_counts_publisher = self.create_publisher(
            Int32MultiArray, '/silorobot/wheel_counts', 10)
        self._adc_publisher = self.create_publisher(
            UInt16MultiArray, '/silorobot/distance_adc', 10)
        self._battery_publisher = self.create_publisher(
            Float32, '/silorobot/battery_voltage', 10)
        self._battery_packs_publisher = self.create_publisher(
            UInt16MultiArray, '/silorobot/battery_pack_mv', 10)
        self._battery_flags_publisher = self.create_publisher(
            UInt8, '/silorobot/battery_flags', 10)
        self._encoder_flags_publisher = self.create_publisher(
            UInt8, '/silorobot/encoder_flags', 10)

        self.create_subscription(
            Twist, '/silorobot/drive_command', self._on_drive_command, 10)
        self.create_subscription(
            Bool, '/silorobot/emergency_stop', self._on_emergency_stop, 10)

        self._serial = None
        self._last_connect_attempt = 0.0
        self._last_command_time = 0.0
        self._throttle = 0
        self._turn = 0
        # STM32는 부팅 직후 정지 래치 상태다. 브릿지가 False로 시작하면 대시보드의
        # stop_release가 _on_emergency_stop의 elif 조건에 걸리지 않아 CMD_STOP_RELEASE가
        # 영원히 나가지 않는다(상태 불일치 버그, 2026-08-18 실기에서 발견).
        self._emergency_latched = True
        self._release_frames_remaining = 0
        self._receive_buffer = bytearray()
        self._connected = False

        self.create_timer(1.0 / self._command_hz, self._command_tick)
        self.create_timer(0.005, self._read_tick)
        self._publish_connection(False)

    def _on_drive_command(self, message):
        self._throttle = self._clamp_axis(message.linear.x)
        self._turn = self._clamp_axis(message.angular.z)
        self._last_command_time = time.monotonic()

    def _on_emergency_stop(self, message):
        if message.data:
            self._emergency_latched = True
            self._release_frames_remaining = 0
        elif self._emergency_latched:
            self._emergency_latched = False
            self._release_frames_remaining = 3

    def _command_tick(self):
        # /silorobot/stm32_connected is a plain volatile-QoS topic: a subscriber that finishes
        # DDS discovery even slightly after this publishes its one edge-triggered value (e.g.
        # every node launched together at boot) never sees it and is stuck believing "offline"
        # forever. Re-publish the current state on every tick so a late joiner is caught up
        # within one command period instead of waiting for the next actual state change.
        self._connected_publisher.publish(Bool(data=self._connected))

        if not self._ensure_serial():
            return

        command = CMD_MOVE
        throttle = self._throttle
        turn = self._turn

        if self._emergency_latched:
            command = CMD_STOP
            throttle = 0
            turn = 0
        elif self._release_frames_remaining > 0:
            command = CMD_STOP_RELEASE
            throttle = 0
            turn = 0
            self._release_frames_remaining -= 1
        elif time.monotonic() - self._last_command_time > self._drive_timeout:
            throttle = 0
            turn = 0

        try:
            self._serial.write(self._make_command_frame(command, throttle, turn))
        except serial.SerialException as error:
            self.get_logger().warn('STM32 write failed: {}'.format(error))
            self._close_serial()

    def _read_tick(self):
        if not self._ensure_serial():
            return

        try:
            received = self._serial.read_all()
        except serial.SerialException as error:
            self.get_logger().warn('STM32 read failed: {}'.format(error))
            self._close_serial()
            return

        if received:
            self._receive_buffer.extend(received)
            self._parse_telemetry_frames()

    def _ensure_serial(self):
        if self._serial is not None and self._serial.is_open:
            return True

        now = time.monotonic()
        if now - self._last_connect_attempt < self._reconnect_sec:
            return False
        self._last_connect_attempt = now

        try:
            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baud_rate,
                timeout=0,
                write_timeout=0.1)
            self._receive_buffer.clear()
            # 재연결은 STM32가 재부팅됐을 수 있다는 뜻이므로 실제 상태(래치)에 다시 맞춘다.
            # 명시적 해제 전까지 움직이지 않는 안전 설계를 유지한다.
            self._emergency_latched = True
            self._release_frames_remaining = 0
            self.get_logger().info(
                'Connected to STM32 VCP: {} @ {}'.format(
                    self._port, self._baud_rate))
            self._publish_connection(True)
            return True
        except (serial.SerialException, OSError) as error:
            self.get_logger().warn(
                'STM32 VCP unavailable (retrying): {}'.format(error))
            self._publish_connection(False)
            return False

    def _close_serial(self):
        if self._serial is not None:
            try:
                self._serial.close()
            except serial.SerialException:
                pass
        self._serial = None
        self._publish_connection(False)

    def _parse_telemetry_frames(self):
        while True:
            starts = [
                index for index in (
                     self._receive_buffer.find(bytes([TELEMETRY_START])),
                     self._receive_buffer.find(bytes([ENCODER_START])),
                     self._receive_buffer.find(bytes([ADC_START])),
                     self._receive_buffer.find(bytes([BATTERY_START])))
                if index >= 0]
            if not starts:
                self._receive_buffer.clear()
                return
            start_index = min(starts)
            if start_index > 0:
                del self._receive_buffer[:start_index]
            frame_start = self._receive_buffer[0]
            frame_length = {
                TELEMETRY_START: 8, ENCODER_START: 13,
                ADC_START: 11, BATTERY_START: 9,
            }[frame_start]
            if len(self._receive_buffer) < frame_length:
                return

            frame = self._receive_buffer[:frame_length]
            if frame[-1] != FRAME_END:
                del self._receive_buffer[0]
                continue
            if self._xor_checksum(frame[1:-2]) != frame[-2]:
                self.get_logger().warn('Discarded STM32 telemetry checksum error')
                del self._receive_buffer[0]
                continue

            if frame_start == TELEMETRY_START:
                if frame[1] != 0x01:
                    del self._receive_buffer[0]
                    continue
                distances = UInt8MultiArray()
                distances.data = [frame[2], frame[3], frame[4]]
                self._distance_publisher.publish(distances)
                self._flags_publisher.publish(UInt8(data=frame[5]))
            elif frame_start == ENCODER_START:
                if frame[1] != 0x02:
                    del self._receive_buffer[0]
                    continue
                counts = Int32MultiArray()
                counts.data = [
                    int.from_bytes(frame[2:6], byteorder='little', signed=True),
                    int.from_bytes(frame[6:10], byteorder='little', signed=True),
                ]
                # frame[10] is encoder-local flags.  It is deliberately not
                # merged into /stm32_flags, whose 0xBB meaning is fixed.
                self._encoder_flags_publisher.publish(UInt8(data=frame[10]))
                self._wheel_counts_publisher.publish(counts)
            elif frame_start == ADC_START:
                if frame[1] != 0x03:
                    del self._receive_buffer[0]
                    continue
                adc = UInt16MultiArray()
                adc.data = [
                    int.from_bytes(frame[2:4], byteorder='little'),
                    int.from_bytes(frame[4:6], byteorder='little'),
                    int.from_bytes(frame[6:8], byteorder='little'),
                ]
                self._adc_publisher.publish(adc)
            else:
                if frame[1] != 0x04:
                    del self._receive_buffer[0]
                    continue
                packs = UInt16MultiArray()
                packs.data = [
                    int.from_bytes(frame[2:4], byteorder='little'),
                    int.from_bytes(frame[4:6], byteorder='little'),
                ]
                flags = int(frame[6])
                self._battery_packs_publisher.publish(packs)
                self._battery_flags_publisher.publish(UInt8(data=flags))
                valid = [packs.data[index] for index in range(2)
                         if flags & (1 << index) and packs.data[index] > 0]
                if valid:
                    self._battery_publisher.publish(
                        Float32(data=min(valid) / 1000.0))
            del self._receive_buffer[:frame_length]

    @staticmethod
    def _make_command_frame(command, throttle, turn):
        throttle_byte = throttle & 0xFF
        turn_byte = turn & 0xFF
        checksum = command ^ throttle_byte ^ turn_byte
        return bytes([
            FRAME_START,
            command,
            throttle_byte,
            turn_byte,
            checksum,
            FRAME_END,
        ])

    @staticmethod
    def _xor_checksum(values):
        checksum = 0
        for value in values:
            checksum ^= value
        return checksum

    @staticmethod
    def _clamp_axis(value):
        return max(-100, min(100, int(round(value))))

    def _publish_connection(self, connected):
        if self._connected == connected:
            return
        self._connected = connected
        self._connected_publisher.publish(Bool(data=connected))

    def destroy_node(self):
        self._close_serial()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = Stm32UartBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
