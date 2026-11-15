#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""Single authority for SiloRobot emergency-stop decisions."""

import json
import math
import time

from sensor_msgs.msg import Imu
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String, UInt8, UInt8MultiArray, UInt16MultiArray

STM_FLAG_STOP_LATCHED = 0x01
STM_FLAG_TIMEOUT_SEEN = 0x02
BATTERY_FLAG_PACK_1_VALID = 0x01
BATTERY_FLAG_PACK_2_VALID = 0x02
BATTERY_FLAG_WARNING = 0x04
BATTERY_FLAG_STOP_LATCHED = 0x08
BATTERY_FLAG_MONITOR_ENABLED = 0x10
RELEASE_CONFIRM_TIMEOUT_S = 1.0


def finite(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) else None


class SafetySupervisor(Node):
    """Monitor telemetry and publish the only emergency_stop topic."""

    def __init__(self):
        super().__init__('safety_supervisor')
        self.declare_parameter('armed', False)
        self.declare_parameter('stale_ms', 300)
        self.declare_parameter('startup_grace_ms', 1500)
        self.declare_parameter('warn_hold_ms', 0)
        self.declare_parameter('stop_hold_ms', 0)
        self.declare_parameter('release_stable_ms', 500)
        # Conservative bootstrap thresholds keep bring-up reproducible. They
        # remain inactive for automatic STOP while armed=false and must be
        # replaced by the 04 §10 measured profile before wall operation.
        self.declare_parameter('distance_spread_warn_mm', 15.0)
        self.declare_parameter('distance_spread_stop_mm', 30.0)
        self.declare_parameter('distance_rate_stop_mm_s', 120.0)
        self.declare_parameter('omega_warn_dps', 60.0)
        self.declare_parameter('omega_stop_dps', 120.0)
        self.declare_parameter('accel_deviation_g', 0.35)
        self.declare_parameter('battery_release_mv', 10200)
        self.declare_parameter('distance_calibration_confirmed', False)
        # Bench-testing the drivetrain before the distance sensors are mounted needs a way to
        # stop treating "no distance data" as a hard OFFLINE/no-release condition. This must
        # never be confused with distance_calibration_confirmed: that flag means "the sensors
        # are there and the numbers are trustworthy"; this one means "the sensors are not
        # installed yet at all, don't require them". Leave true for any run with sensors mounted.
        self.declare_parameter('require_distance', True)
        self._params = {name: self.get_parameter(name).value for name in (
            'armed', 'stale_ms', 'startup_grace_ms', 'warn_hold_ms',
            'stop_hold_ms', 'release_stable_ms', 'distance_spread_warn_mm',
            'distance_spread_stop_mm', 'distance_rate_stop_mm_s',
            'omega_warn_dps', 'omega_stop_dps', 'accel_deviation_g',
            'battery_release_mv', 'distance_calibration_confirmed',
            'require_distance')}
        self._state_publisher = self.create_publisher(
            String, '/silorobot/safety_state', 10)
        self._stop_publisher = self.create_publisher(
            Bool, '/silorobot/emergency_stop', 10)
        self.create_subscription(Imu, '/silorobot/imu', self._on_imu, 10)
        self.create_subscription(String, '/silorobot/imu_health', self._on_health, 10)
        self.create_subscription(UInt8MultiArray, '/silorobot/distances_mm',
                                 self._on_distances, 10)
        self.create_subscription(UInt8, '/silorobot/stm32_flags', self._on_flags, 10)
        self.create_subscription(Bool, '/silorobot/stm32_connected',
                                 self._on_stm_connected, 10)
        self.create_subscription(Bool, '/silorobot/stop_request',
                                 self._on_stop_request, 10)
        self.create_subscription(UInt16MultiArray, '/silorobot/battery_pack_mv',
                                 self._on_battery_packs, 10)
        self.create_subscription(UInt8, '/silorobot/battery_flags',
                                 self._on_battery_flags, 10)
        self._started_at = time.monotonic()
        self._state = 'OFFLINE'
        self._state_since = self._started_at
        # STM32 and stm32_uart_bridge both boot/reconnect latched. Mirror the
        # physical state so software never reports an unsafe false release.
        self._latched = True
        self._release_requested = False
        self._release_pulse = False
        self._release_stable_since = None
        self._imu = None
        self._imu_at = None
        self._imu_health = {}
        self._distance = [0, 0, 0]
        self._distance_at = None
        self._previous_mean = None
        self._previous_mean_at = None
        self._mean_rate = None
        self._stm_connected = False
        self._stm_flags = 0
        self._stm_flags_at = None
        self._release_confirm_deadline = None
        self._battery_packs_mv = [0, 0]
        self._battery_flags = 0
        self._battery_at = None
        self._battery_monitor_seen = False
        self.create_timer(0.1, self._tick)

    def _on_imu(self, message):
        self._imu = message
        self._imu_at = time.monotonic()

    def _on_health(self, message):
        try:
            parsed = json.loads(message.data)
        except (TypeError, ValueError):
            return
        if isinstance(parsed, dict):
            self._imu_health = parsed

    def _on_distances(self, message):
        values = [int(value) for value in list(message.data)[:3]]
        while len(values) < 3:
            values.append(0)
        now = time.monotonic()
        valid = [value for value in values if value > 0]
        if valid:
            mean = sum(valid) / len(valid)
            if self._previous_mean is not None and now > self._previous_mean_at:
                self._mean_rate = (mean - self._previous_mean) / (now - self._previous_mean_at)
            self._previous_mean, self._previous_mean_at = mean, now
        self._distance, self._distance_at = values, now

    def _on_flags(self, message):
        self._stm_flags = int(message.data)
        self._stm_flags_at = time.monotonic()
        if not (self._stm_flags & STM_FLAG_STOP_LATCHED):
            self._release_confirm_deadline = None

    def _on_stm_connected(self, message):
        self._stm_connected = bool(message.data)

    def _on_battery_packs(self, message):
        values = [int(value) for value in list(message.data)[:2]]
        while len(values) < 2:
            values.append(0)
        self._battery_packs_mv = values
        self._battery_at = time.monotonic()

    def _on_battery_flags(self, message):
        self._battery_flags = int(message.data) & 0xff
        self._battery_at = time.monotonic()
        if self._battery_flags & BATTERY_FLAG_MONITOR_ENABLED:
            self._battery_monitor_seen = True

    def _on_stop_request(self, message):
        if message.data:
            self._latched = True
            self._release_requested = False
            self._release_confirm_deadline = None
        else:
            self._release_requested = True

    def _age_ms(self, timestamp):
        return None if timestamp is None else int((time.monotonic() - timestamp) * 1000)

    def _distance_meta(self):
        valid = [value > 0 for value in self._distance]
        values = [value for value in self._distance if value > 0]
        return {
            'valid': valid, 'unit': 'mm',
            'calibrated': bool(self._params['distance_calibration_confirmed']),
            'calibration_source': ('MEASURED' if self._params['distance_calibration_confirmed']
                                   else 'DATASHEET_ESTIMATE'),
            'mean': sum(values) / len(values) if values else None,
            'spread': max(values) - min(values) if values else None,
            'mean_rate': self._mean_rate,
            'age_ms': self._age_ms(self._distance_at),
        }

    def _imu_meta(self):
        age = self._age_ms(self._imu_at)
        gyro = None
        accel_deviation = None
        if self._imu is not None:
            gyro = math.degrees(math.sqrt(
                self._imu.angular_velocity.x ** 2 + self._imu.angular_velocity.y ** 2 +
                self._imu.angular_velocity.z ** 2))
            accel_g = math.sqrt(
                self._imu.linear_acceleration.x ** 2 + self._imu.linear_acceleration.y ** 2 +
                self._imu.linear_acceleration.z ** 2) / 9.80665
            accel_deviation = abs(accel_g - 1.0)
        health_valid = bool(self._imu_health.get('valid', self._imu is not None))
        valid = health_valid and age is not None and age <= self._params['stale_ms']
        return {'valid': bool(valid),
                'age_ms': age, 'gyro_mag_dps': gyro,
                'accel_deviation_g': accel_deviation}

    def _battery_meta(self):
        flags = self._battery_flags
        age = self._age_ms(self._battery_at)
        fresh = age is not None and age <= 1500
        return {
            'enabled': self._battery_monitor_seen,
            'fresh': fresh,
            'age_ms': age,
            'packs_mv': list(self._battery_packs_mv),
            'valid': [bool(flags & BATTERY_FLAG_PACK_1_VALID),
                      bool(flags & BATTERY_FLAG_PACK_2_VALID)],
            'warning': bool(flags & BATTERY_FLAG_WARNING),
            'stop_latched': bool(flags & BATTERY_FLAG_STOP_LATCHED),
        }

    @staticmethod
    def _above(value, threshold):
        return value is not None and threshold > 0 and value > threshold

    def _evaluate(self):
        distance = self._distance_meta()
        imu = self._imu_meta()
        battery = self._battery_meta()
        stale = self._params['stale_ms']
        require_distance = bool(self._params['require_distance'])
        distance_fresh = distance['age_ms'] is not None and distance['age_ms'] <= stale
        valid_count = sum(distance['valid'])
        if not require_distance:
            # Sensors physically not mounted yet: treat distance as vacuously satisfied
            # instead of a permanent OFFLINE/no-release condition.
            distance_fresh = True
            valid_count = 3
        reasons = []
        if not self._stm_connected:
            reasons.append('stm32_offline')
        flags_fresh = (self._age_ms(self._stm_flags_at) is not None and
                       self._age_ms(self._stm_flags_at) <= stale)
        stm_stop_latched = bool(self._stm_flags & STM_FLAG_STOP_LATCHED)
        if not flags_fresh:
            reasons.append('stm32_flags_stale')
        if self._stm_flags & STM_FLAG_TIMEOUT_SEEN:
            reasons.append('stm32_timeout_seen')
        if battery['enabled'] and not battery['fresh']:
            reasons.append('battery_stale')
        if battery['enabled'] and battery['fresh'] and not all(battery['valid']):
            reasons.append('battery_invalid')
        if battery['warning']:
            reasons.append('battery_warning')
        if battery['stop_latched']:
            reasons.append('battery_stop_latched')
        if not require_distance:
            reasons.append('distance_not_required')
        elif not distance_fresh:
            reasons.append('distance_stale')
        elif valid_count < 3:
            reasons.append('distance_invalid')
        if not imu['valid']:
            reasons.append('imu_stale')
        spread_warn = self._above(distance['spread'], self._params['distance_spread_warn_mm'])
        spread_stop = self._above(distance['spread'], self._params['distance_spread_stop_mm'])
        leaving = self._above(distance['mean_rate'], self._params['distance_rate_stop_mm_s'])
        gyro_warn = self._above(imu['gyro_mag_dps'], self._params['omega_warn_dps'])
        gyro_stop = self._above(imu['gyro_mag_dps'], self._params['omega_stop_dps'])
        accel_spike = self._above(imu['accel_deviation_g'], self._params['accel_deviation_g'])
        if spread_warn:
            reasons.append('spread_high')
        if gyro_warn:
            reasons.append('gyro_spike')
        if accel_spike:
            reasons.append('accel_spike')
        severe = (valid_count <= 1 or (spread_stop and (gyro_warn or accel_spike)) or
                  (leaving and (gyro_warn or accel_spike)) or gyro_stop)
        # IMU is optional for mobility: unavailable IMU makes monitoring
        # explicit, but cannot silently invent a STOP threshold.
        offline = not self._stm_connected or not distance_fresh
        monitor_armed = bool(self._params['armed'] and distance_fresh)
        if time.monotonic() - self._started_at < self._params['startup_grace_ms'] / 1000.0:
            monitor_armed = False
            reasons.append('startup_grace')
        if self._latched:
            return 'STOPPED', reasons or ['manual_stop'], distance, imu, battery, monitor_armed
        if not flags_fresh:
            return 'OFFLINE', reasons, distance, imu, battery, monitor_armed
        if stm_stop_latched:
            if (self._release_confirm_deadline is not None and
                    time.monotonic() <= self._release_confirm_deadline):
                reasons.append('release_waiting_stm32')
                return 'RELEASING', reasons, distance, imu, battery, monitor_armed
            reasons.append('stm32_stop_latched')
            return 'STOPPED', reasons, distance, imu, battery, monitor_armed
        if offline:
            return 'OFFLINE', reasons, distance, imu, battery, monitor_armed
        if severe and monitor_armed:
            return 'STOPPED', reasons or ['sensor_danger'], distance, imu, battery, monitor_armed
        if (spread_warn or gyro_warn or valid_count == 2) and monitor_armed:
            return 'WARNING', reasons, distance, imu, battery, monitor_armed
        return 'NORMAL', reasons, distance, imu, battery, monitor_armed

    def _release_allowed(self, distance, imu):
        """Manual release needs live, non-dangerous telemetry, not armed mode."""
        require_distance = bool(self._params['require_distance'])
        if not self._stm_connected:
            return False
        flags_age = self._age_ms(self._stm_flags_at)
        if flags_age is None or flags_age > self._params['stale_ms']:
            return False
        if not (self._stm_flags & STM_FLAG_STOP_LATCHED):
            return False
        if require_distance:
            if distance['age_ms'] is None:
                return False
            if not distance['calibrated']:
                return False
            if distance['age_ms'] > self._params['stale_ms']:
                return False
            if sum(distance['valid']) < 2:
                return False
            if self._above(distance['spread'], self._params['distance_spread_stop_mm']):
                return False
            if self._above(distance['mean_rate'], self._params['distance_rate_stop_mm_s']):
                return False
        if self._above(imu['gyro_mag_dps'], self._params['omega_stop_dps']):
            return False
        battery = self._battery_meta()
        if battery['enabled']:
            if not battery['fresh'] or not all(battery['valid']):
                return False
            # bit3 is intentionally *not* a rejection condition: it records that STM32
            # stopped for low voltage and can only be cleared by the very release command
            # this method gates.  Require present voltage above the same recovery threshold
            # instead; otherwise Nano and STM32 deadlock forever after a recovered battery.
            if min(battery['packs_mv']) < self._params['battery_release_mv']:
                return False
        return True

    def _tick(self):
        candidate, reasons, distance, imu, battery, armed = self._evaluate()
        self._release_pulse = False
        sensors_stable = self._release_allowed(distance, imu)
        now = time.monotonic()
        if sensors_stable:
            if self._release_stable_since is None:
                self._release_stable_since = now
        else:
            self._release_stable_since = None
        stable_ms = (0 if self._release_stable_since is None else
                     int((now - self._release_stable_since) * 1000))
        release_ready = sensors_stable and stable_ms >= self._params['release_stable_ms']
        if self._release_requested:
            if not self._latched:
                reasons = list(reasons) + ['release_waiting_stm32']
                self._release_requested = False
            elif release_ready:
                self._latched = False
                self._release_requested = False
                self._release_pulse = True
                self._release_confirm_deadline = now + RELEASE_CONFIRM_TIMEOUT_S
                candidate, reasons, distance, imu, battery, armed = self._evaluate()
            elif not sensors_stable:
                reasons = list(reasons) + ['release_rejected']
                self._release_requested = False
            else:
                reasons = list(reasons) + ['release_waiting_stable']
        if candidate == 'STOPPED':
            self._latched = True
        if candidate != self._state:
            self._state, self._state_since = candidate, time.monotonic()
        if self._latched:
            self._stop_publisher.publish(Bool(data=True))
        elif self._release_pulse:
            # STM bridge emits the required three release frames from this one
            # state transition; no other node is allowed to publish this topic.
            self._stop_publisher.publish(Bool(data=False))
        payload = {
            'state': self._state, 'reasons': reasons, 'latched': self._latched,
            'armed': armed, 'since_ms': int(self._state_since * 1000),
            'distance_meta': distance, 'imu_meta': imu, 'battery_meta': battery,
            'stm32': {'connected': self._stm_connected,
                      'stop_latched': bool(self._stm_flags & STM_FLAG_STOP_LATCHED),
                      'timeout_seen': bool(self._stm_flags & STM_FLAG_TIMEOUT_SEEN),
                      'flags_age_ms': self._age_ms(self._stm_flags_at)},
        }
        self._state_publisher.publish(String(data=json.dumps(payload, allow_nan=False)))


def main(args=None):
    rclpy.init(args=args)
    node = SafetySupervisor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
