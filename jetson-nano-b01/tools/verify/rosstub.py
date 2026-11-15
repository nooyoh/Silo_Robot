"""Minimal ROS2 stand-ins so the real Nano nodes can be imported and driven off-robot.

The point of the harness is to exercise the shipped source files unmodified, so this
fakes just enough of rclpy/std_msgs/geometry_msgs/sensor_msgs for them to construct.
"""

import sys
import types


class _Value:
    def __init__(self, value):
        self.value = value

    def get_parameter_value(self):
        return self

    @property
    def string_value(self):
        return self.value


class _Logger:
    def __init__(self):
        self.messages = []

    def info(self, text):
        self.messages.append(('info', text))

    def warn(self, text):
        self.messages.append(('warn', text))

    def error(self, text):
        self.messages.append(('error', text))


class _Publisher:
    def __init__(self, topic):
        self.topic = topic
        self.sent = []

    def publish(self, message):
        self.sent.append(message)

    def last(self):
        return self.sent[-1] if self.sent else None


class Node:
    """Records publishers/subscriptions/timers so the harness can drive them by hand."""

    PARAM_OVERRIDES = {}

    def __init__(self, name):
        self._name = name
        self._params = {}
        self.publishers_by_topic = {}
        self.subscriptions_by_topic = {}
        self.timers = []
        self._logger = _Logger()

    def declare_parameter(self, name, default=None):
        override = self.PARAM_OVERRIDES.get(self._name, {})
        self._params[name] = override.get(name, default)

    def get_parameter(self, name):
        return _Value(self._params.get(name))

    def create_publisher(self, msg_type, topic, qos=10):
        publisher = _Publisher(topic)
        self.publishers_by_topic[topic] = publisher
        return publisher

    def create_subscription(self, msg_type, topic, callback, qos=10):
        self.subscriptions_by_topic[topic] = callback
        return callback

    def create_timer(self, period, callback):
        self.timers.append((period, callback))
        return callback

    def get_logger(self):
        return self._logger

    def destroy_node(self):
        pass


class _Vec3:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0


class Twist:
    def __init__(self):
        self.linear = _Vec3()
        self.angular = _Vec3()


class _Msg:
    def __init__(self, data=None):
        self.data = data


class String(_Msg):
    pass


class Bool(_Msg):
    pass


class UInt8(_Msg):
    pass


class Float32(_Msg):
    pass


class UInt8MultiArray(_Msg):
    pass


class UInt16MultiArray(_Msg):
    pass


class Int32MultiArray(_Msg):
    pass


class _Quat:
    def __init__(self):
        self.x = self.y = self.z = 0.0
        self.w = 1.0


class Imu:
    def __init__(self):
        self.orientation = _Quat()
        self.angular_velocity = _Vec3()
        self.linear_acceleration = _Vec3()
        self.orientation_covariance = [0.0] * 9
        self.angular_velocity_covariance = [0.0] * 9
        self.linear_acceleration_covariance = [0.0] * 9
        self.header = types.SimpleNamespace(
            stamp=None, frame_id='')


def install():
    """Register the fakes in sys.modules so plain `import rclpy` etc. resolve to them."""
    rclpy = types.ModuleType('rclpy')
    rclpy.init = lambda *a, **k: None
    rclpy.shutdown = lambda *a, **k: None
    rclpy.spin = lambda *a, **k: None
    rclpy.ok = lambda: True
    rclpy.spin_once = lambda *a, **k: None
    node_mod = types.ModuleType('rclpy.node')
    node_mod.Node = Node
    rclpy.node = node_mod

    std_msgs = types.ModuleType('std_msgs')
    std_msgs_msg = types.ModuleType('std_msgs.msg')
    for cls in (String, Bool, Float32, UInt8, UInt8MultiArray,
                UInt16MultiArray, Int32MultiArray):
        setattr(std_msgs_msg, cls.__name__, cls)
    std_msgs.msg = std_msgs_msg

    geometry = types.ModuleType('geometry_msgs')
    geometry_msg = types.ModuleType('geometry_msgs.msg')
    geometry_msg.Twist = Twist
    geometry.msg = geometry_msg

    sensor = types.ModuleType('sensor_msgs')
    sensor_msg = types.ModuleType('sensor_msgs.msg')
    sensor_msg.Imu = Imu
    sensor.msg = sensor_msg

    serial = types.ModuleType('serial')
    serial.Serial = object
    serial.SerialException = Exception

    for name, module in [
            ('rclpy', rclpy), ('rclpy.node', node_mod),
            ('std_msgs', std_msgs), ('std_msgs.msg', std_msgs_msg),
            ('geometry_msgs', geometry), ('geometry_msgs.msg', geometry_msg),
            ('sensor_msgs', sensor), ('sensor_msgs.msg', sensor_msg),
            ('serial', serial)]:
        sys.modules[name] = module
