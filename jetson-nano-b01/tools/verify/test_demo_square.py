#!/usr/bin/env python3
"""Off-robot checks for the shipped open-loop filming fallback."""

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PKG = os.path.join(REPO, 'src', 'silorobot_nano', 'silorobot_nano')

sys.path.insert(0, HERE)
import rosstub  # noqa: E402

rosstub.install()


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def load_demo(clock):
    spec = importlib.util.spec_from_file_location(
        'silo_demo_square', os.path.join(PKG, 'demo_square.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.time = clock
    return module


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    print('  [PASS] ' + label)


clock = FakeClock()
demo = load_demo(clock)
PARAM_OVERRIDES = {
    'demo_square': {
        'start_delay_sec': 1.0,
        'release_timeout_sec': 2.0,
        'side_seconds': 0.1,
        'turn_seconds': 0.1,
        'settle_seconds': 0.05,
        'straight_command': 50.0,
        'turn_command': 40.0,
    },
}
rosstub.Node.PARAM_OVERRIDES = PARAM_OVERRIDES

segments = demo.make_square_segments(1.0, 0.5, 0.1, 50.0, 40.0)
check(len(segments) == 16, '4 straight + 4 turn + 8 settle segments')
check(sum(1 for segment in segments if segment[2] != 0) == 4,
      'exactly four straight legs')
check(sum(1 for segment in segments if segment[3] != 0) == 4,
      'exactly four right turns')
ten_second_segments = demo.make_square_segments(1.5, 0.6, 0.2, 50.0, 40.0)
check(abs(sum(segment[1] for segment in ten_second_segments) - 10.0) < 1e-9,
      'default visible execution lasts 10 seconds')

node = demo.DemoSquare()
drive = node.publishers_by_topic['/silorobot/drive_command']
release = node.publishers_by_topic['/silorobot/stop_request']
plan_pub = node.publishers_by_topic['/silorobot/plan']
state_pub = node.publishers_by_topic['/silorobot/mission_state']
node._tick()
check(release.last() is not None and release.last().data is False,
      'startup requests one safe latch release path')
plan = json.loads(plan_pub.last().data)
check(plan['width_m'] == 0.5 and plan['height_m'] == 0.5,
      'dashboard receives a 0.5 x 0.5 m plan')
check(len(plan['waypoints']) == 5 and plan['waypoints'][0] == plan['waypoints'][-1],
      'planner-screen route closes the square')
node._on_emergency_stop(rosstub.Bool(False))
clock.advance(1.01)
for _ in range(100):
    node._tick()
    clock.advance(0.05)
    if node._complete:
        break
node._tick()
check(node._complete and not node._aborted, 'square sequence reaches COMPLETE')
check(any(message.linear.x == 50.0 for message in drive.sent),
      'straight command is published')
check(any(message.angular.z == 40.0 for message in drive.sent),
      'turn command is published')
check(drive.last().linear.x == 0.0 and drive.last().angular.z == 0.0,
      'completion publishes an explicit stop')
states = [json.loads(message.data) for message in state_pub.sent]
running_poses = [state['plan_pose'] for state in states
                 if state['state'] == 'RUNNING']
check(len({(round(pose['x'], 3), round(pose['y'], 3))
           for pose in running_poses}) > 4,
      'planner-screen live marker moves continuously')
check(states[-1]['state'] == 'COMPLETE' and
      states[-1]['current_waypoint'] == states[-1]['total_waypoints'],
      'dashboard progress reaches COMPLETE')

clock2 = FakeClock()
demo2 = load_demo(clock2)
rosstub.Node.PARAM_OVERRIDES = PARAM_OVERRIDES
node2 = demo2.DemoSquare()
node2._tick()
node2._on_emergency_stop(rosstub.Bool(False))
clock2.advance(1.01)
node2._tick()
node2._on_emergency_stop(rosstub.Bool(True))
node2._tick()
stopped = node2.publishers_by_topic['/silorobot/drive_command'].last()
check(node2._aborted, 'post-release emergency stop aborts permanently')
check(stopped.linear.x == 0.0 and stopped.angular.z == 0.0,
      'emergency abort publishes zero command')

print('demo-square checks passed')
