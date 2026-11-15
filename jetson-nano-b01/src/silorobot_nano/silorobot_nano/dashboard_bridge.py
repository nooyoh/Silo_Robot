#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""Bridge the RPi4 dashboard WebSocket protocol into local ROS2 topics."""

import asyncio
import json
import math
import queue
import threading
import time

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import (Bool, Float32, String, UInt8, UInt8MultiArray,
                          UInt16MultiArray)
import websockets


DEFAULT_DASHBOARD_URI = 'ws://100.74.141.112:8765'


class DashboardBridge(Node):
    """Reconnect to the dashboard and translate its JSON contract to ROS2."""

    def __init__(self):
        super().__init__('dashboard_bridge')

        self.declare_parameter('dashboard_uri', DEFAULT_DASHBOARD_URI)
        self._dashboard_uri = self.get_parameter(
            'dashboard_uri').get_parameter_value().string_value

        self._drive_publisher = self.create_publisher(
            Twist, '/silorobot/drive_command', 10)
        self._stop_request_publisher = self.create_publisher(
            Bool, '/silorobot/stop_request', 10)
        self._plan_request_publisher = self.create_publisher(
            String, '/silorobot/route_plan_request', 10)
        self._autonomy_command_publisher = self.create_publisher(
            String, '/silorobot/autonomy_command', 10)

        self.create_subscription(
            Imu, '/silorobot/imu', self._on_imu, 10)
        self.create_subscription(
            String, '/silorobot/imu_health', self._on_imu_health, 10)
        self.create_subscription(
            UInt8MultiArray, '/silorobot/distances_mm',
            self._on_distances, 10)
        self.create_subscription(
            Bool, '/silorobot/stm32_connected',
            self._on_stm32_connected, 10)
        self.create_subscription(
            String, '/silorobot/safety_state', self._on_safety_state, 10)
        self.create_subscription(
            String, '/silorobot/mission_state', self._on_mission_state, 10)
        self.create_subscription(
            String, '/silorobot/plan', self._on_plan, 10)
        self.create_subscription(
            String, '/silorobot/pose', self._on_pose, 10)
        self.create_subscription(
            Float32, '/silorobot/battery_voltage', self._on_battery_voltage, 10)
        self.create_subscription(
            UInt16MultiArray, '/silorobot/battery_pack_mv',
            self._on_battery_packs, 10)
        self.create_subscription(
            UInt8, '/silorobot/battery_flags', self._on_battery_flags, 10)

        self._state_lock = threading.Lock()
        self._imu = {
            'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0,
            'gx': 0.0, 'gy': 0.0, 'gz': 0.0,
            'ax': 0.0, 'ay': 0.0, 'az': 0.0,
            'valid': False, 'age_ms': None,
        }
        self._distances = [0, 0, 0]
        self._stm32_connected = False
        self._safety_state = self._default_safety_state()
        self._autonomy_mode = 'MANUAL'
        self._mission_state = {
            'mode': 'MANUAL', 'state': 'IDLE', 'plan_id': None,
            'current_waypoint': 0, 'total_waypoints': 0,
            'coverage_ratio': 0.0,
        }
        self._plan = None
        self._pose = None
        self._battery_voltage = None
        self._battery_packs_mv = [0, 0]
        self._battery_flags = 0
        self._battery_at = None
        self._incoming_commands = queue.Queue()
        self._shutdown_requested = threading.Event()

        self.create_timer(0.02, self._publish_pending_commands)
        self._worker = threading.Thread(
            target=self._network_worker,
            name='dashboard-websocket',
            daemon=True)
        self._worker.start()
        self.get_logger().info(
            'Dashboard bridge started: {}'.format(self._dashboard_uri))

    def _on_imu(self, message):
        roll, pitch, yaw = self._quaternion_to_euler(message)
        values = {
            'roll': roll, 'pitch': pitch, 'yaw': yaw,
            # ROS Imu is rad/s and m/s^2; dashboard v2 uses displayed
            # degrees/s and g, matching the WT901C source data.
            'gx': math.degrees(message.angular_velocity.x),
            'gy': math.degrees(message.angular_velocity.y),
            'gz': math.degrees(message.angular_velocity.z),
            'ax': message.linear_acceleration.x / 9.80665,
            'ay': message.linear_acceleration.y / 9.80665,
            'az': message.linear_acceleration.z / 9.80665,
        }
        if not all(math.isfinite(value) for value in values.values()):
            return
        with self._state_lock:
            self._imu.update(values)

    def _on_imu_health(self, message):
        try:
            health = json.loads(message.data)
        except (TypeError, ValueError):
            return
        if not isinstance(health, dict):
            return
        with self._state_lock:
            self._imu['valid'] = bool(health.get('valid', False))
            self._imu['age_ms'] = health.get('last_sample_age_ms')

    def _on_distances(self, message):
        values = [int(value) for value in list(message.data)[:3]]
        while len(values) < 3:
            values.append(0)
        with self._state_lock:
            self._distances = values

    def _on_stm32_connected(self, message):
        with self._state_lock:
            self._stm32_connected = bool(message.data)

    def _on_safety_state(self, message):
        try:
            state = json.loads(message.data)
        except (TypeError, ValueError):
            return
        if not isinstance(state, dict):
            return
        with self._state_lock:
            self._safety_state = state

    def _on_mission_state(self, message):
        try:
            state = json.loads(message.data)
        except (TypeError, ValueError):
            return
        if isinstance(state, dict):
            with self._state_lock:
                self._mission_state = state
                self._autonomy_mode = state.get('mode', 'MANUAL')

    def _on_plan(self, message):
        try:
            plan = json.loads(message.data)
        except (TypeError, ValueError):
            return
        if isinstance(plan, dict):
            with self._state_lock:
                self._plan = plan

    def _on_pose(self, message):
        try:
            pose = json.loads(message.data)
        except (TypeError, ValueError):
            return
        if isinstance(pose, dict):
            with self._state_lock:
                self._pose = pose

    def _on_battery_voltage(self, message):
        value = float(message.data)
        if not math.isfinite(value) or value <= 0.0:
            return
        with self._state_lock:
            self._battery_voltage = value
            self._battery_at = time.monotonic()

    def _on_battery_packs(self, message):
        values = [int(value) for value in list(message.data)[:2]]
        while len(values) < 2:
            values.append(0)
        with self._state_lock:
            self._battery_packs_mv = values
            self._battery_at = time.monotonic()

    def _on_battery_flags(self, message):
        with self._state_lock:
            self._battery_flags = int(message.data) & 0xff
            self._battery_at = time.monotonic()

    @staticmethod
    def _default_safety_state():
        return {
            'state': 'OFFLINE', 'reasons': ['awaiting_sensors'],
            'latched': True, 'armed': False,
            'distance_meta': {
                'valid': [False, False, False], 'unit': 'mm',
                'calibrated': False, 'mean': None, 'spread': None,
                'mean_rate': None, 'age_ms': None,
            },
            'stm32': {
                'connected': False, 'stop_latched': True,
                'timeout_seen': False,
            },
        }

    @staticmethod
    def _quaternion_to_euler(message):
        x = message.orientation.x
        y = message.orientation.y
        z = message.orientation.z
        w = message.orientation.w

        sinr_cosp = 2.0 * (w * x + y * z)
        cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
        roll = math.degrees(math.atan2(sinr_cosp, cosr_cosp))

        sinp = 2.0 * (w * y - z * x)
        if abs(sinp) >= 1.0:
            pitch = math.degrees(math.copysign(math.pi / 2.0, sinp))
        else:
            pitch = math.degrees(math.asin(sinp))

        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        yaw = math.degrees(math.atan2(siny_cosp, cosy_cosp))
        return roll, pitch, yaw

    def _status_message(self):
        with self._state_lock:
            battery_age_ms = (None if self._battery_at is None else
                              int((time.monotonic() - self._battery_at) * 1000))
            battery_fresh = battery_age_ms is not None and battery_age_ms <= 1500
            battery_valid = [bool(self._battery_flags & 0x01),
                             bool(self._battery_flags & 0x02)]
            battery_voltage = (
                self._battery_voltage if battery_fresh and any(battery_valid) else None)
            status = {
                'type': 'status',
                'timestamp_ms': int(time.time() * 1000),
                'battery': battery_voltage,
                'battery_meta': {
                    'packs_mv': list(self._battery_packs_mv),
                    'valid': battery_valid,
                    'warning': bool(self._battery_flags & 0x04),
                    'stop_latched': bool(self._battery_flags & 0x08),
                    'enabled': bool(self._battery_flags & 0x10),
                    'age_ms': battery_age_ms,
                    'fresh': battery_fresh,
                },
                'imu': dict(self._imu),
                'distance': list(self._distances),
                'distance_meta': self._safety_state.get('distance_meta'),
                'safety': {
                    key: self._safety_state.get(key)
                    for key in ('state', 'reasons', 'latched', 'armed')
                },
                'stm32': self._safety_state.get('stm32'),
                'connected': self._stm32_connected,
                'mission': dict(self._mission_state),
                'plan': dict(self._plan) if self._plan is not None else None,
                'pose': dict(self._pose) if self._pose is not None else None,
            }
        return json.dumps(status, allow_nan=False)

    def _publish_pending_commands(self):
        while True:
            try:
                payload = self._incoming_commands.get_nowait()
            except queue.Empty:
                return

            message_type = payload.get('type')
            if message_type == 'move':
                # Manual and autonomous commands must never race on the same
                # ROS topic. route_start flips this guard synchronously, and
                # mission_state keeps it aligned through pause/completion.
                if self._autonomy_mode != 'MANUAL':
                    continue
                drive = Twist()
                drive.linear.x = float(self._clamp_axis(
                    payload.get('throttle', 0)))
                drive.angular.z = float(self._clamp_axis(
                    payload.get('turn', 0)))
                self._drive_publisher.publish(drive)
            elif message_type == 'stop':
                self._stop_request_publisher.publish(Bool(data=True))
            elif message_type == 'stop_release':
                self._stop_request_publisher.publish(Bool(data=False))
            elif message_type == 'route_plan_request':
                self._plan_request_publisher.publish(
                    String(data=json.dumps(payload, allow_nan=False)))
            elif message_type in ('route_start', 'route_pause', 'route_resume',
                                  'route_cancel'):
                if message_type == 'route_start':
                    self._autonomy_mode = 'AUTO'
                elif message_type == 'route_cancel':
                    self._autonomy_mode = 'MANUAL'
                    with self._state_lock:
                        self._plan = None
                self._autonomy_command_publisher.publish(
                    String(data=json.dumps(payload, allow_nan=False)))
            else:
                self.get_logger().warn(
                    'Ignoring unknown dashboard message: {}'.format(
                        message_type))

    @staticmethod
    def _clamp_axis(value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return 0
        return max(-100, min(100, value))

    def _network_worker(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._connection_loop())
        finally:
            loop.close()

    async def _connection_loop(self):
        while not self._shutdown_requested.is_set():
            try:
                async with websockets.connect(
                        self._dashboard_uri) as socket:
                    self.get_logger().info('Connected to dashboard WebSocket')
                    next_status_at = 0.0

                    while not self._shutdown_requested.is_set():
                        event_loop = asyncio.get_event_loop()
                        now = event_loop.time()
                        if now >= next_status_at:
                            await socket.send(self._status_message())
                            next_status_at = now + 0.1

                        timeout = max(0.01, next_status_at - event_loop.time())
                        try:
                            raw_message = await asyncio.wait_for(
                                socket.recv(), timeout=timeout)
                        except asyncio.TimeoutError:
                            continue

                        try:
                            payload = json.loads(raw_message)
                        except (TypeError, ValueError):
                            self.get_logger().warn(
                                'Ignoring invalid dashboard JSON message')
                            continue

                        if isinstance(payload, dict):
                            self._incoming_commands.put(payload)
            except Exception as error:
                if not self._shutdown_requested.is_set():
                    self.get_logger().warn(
                        'Dashboard unavailable (retrying in 2 s): {}'.format(
                            error))
                    await asyncio.sleep(2.0)

    def destroy_node(self):
        self._shutdown_requested.set()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = DashboardBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
