"""A-to-Z verification of the SiloRobot autonomy chain, driving the SHIPPED source.

Nothing here reimplements the logic under test: coverage_planner, odometry_node and
path_follower are imported from the actual repo files, and the arcade mixing comes from
the real STM32 C compiled into a DLL. Only the physics of the robot and the encoder
hardware convention are modelled, because those are the parts that live in the world.
"""

import ctypes
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
NANO = os.path.join(REPO, 'src', 'silorobot_nano')
PKG = os.path.join(NANO, 'silorobot_nano')
LIBNAME = 'silofw.dll' if sys.platform == 'win32' else 'libsilofw.so'

sys.path.insert(0, HERE)
import rosstub  # noqa: E402

rosstub.install()

_mix = ctypes.CDLL(os.path.join(HERE, LIBNAME))
_mix.silo_mix.argtypes = [ctypes.c_int, ctypes.c_int,
                          ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]

FAILURES = []
CHECKS = [0]


def check(condition, label, detail=''):
    CHECKS[0] += 1
    if condition:
        print('  [PASS] {}{}'.format(label, (' — ' + detail) if detail else ''))
    else:
        print('  [FAIL] {}{}'.format(label, (' — ' + detail) if detail else ''))
        FAILURES.append(label)


def load(name):
    """Import a node module straight from the repo file."""
    spec = importlib.util.spec_from_file_location(
        'silo_' + name, os.path.join(PKG, name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_bootstrap(path):
    """Read the shipped YAML profile without needing PyYAML on this machine."""
    params, node, in_params = {}, None, False
    for raw in open(path, encoding='utf-8'):
        line = raw.split('#')[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        text = line.strip()
        if indent == 0 and text.endswith(':'):
            node = text[:-1]
            params[node] = {}
            in_params = False
        elif indent == 2 and text == 'ros__parameters:':
            in_params = True
        elif in_params and ':' in text:
            key, _, value = text.partition(':')
            value = value.strip()
            if value in ('true', 'false'):
                parsed = value == 'true'
            else:
                try:
                    parsed = float(value) if ('.' in value or 'e' in value) else int(value)
                except ValueError:
                    parsed = value
            params[node][key.strip()] = parsed
    return params


def stm32_mix(throttle, turn):
    """Real firmware mixing: axis commands -> signed left/right permille."""
    left, right = ctypes.c_int(), ctypes.c_int()
    _mix.silo_mix(int(throttle), int(turn), ctypes.byref(left), ctypes.byref(right))
    return left.value, right.value


BOOTSTRAP = parse_bootstrap(os.path.join(NANO, 'config', 'bootstrap.yaml'))
rosstub.Node.PARAM_OVERRIDES = BOOTSTRAP

coverage_planner = load('coverage_planner')
odometry_node = load('odometry_node')
path_follower = load('path_follower')


class FakeClock:
    """The harness steps far faster than Windows' ~15 ms monotonic resolution, which trips
    odometry_node's `now <= previous_at` guard and silently freezes the pose. Drive an
    explicit clock instead so simulated time advances exactly one control period per tick."""

    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


CLOCK = FakeClock()
odometry_node.time = CLOCK
path_follower.time = CLOCK

SCALE_L = BOOTSTRAP['odometry_node']['meters_per_count_left']
SCALE_R = BOOTSTRAP['odometry_node']['meters_per_count_right']
TRACK_W = BOOTSTRAP['odometry_node']['track_width_m']
# Hardware convention established from the 2026-08-21 captures: a track driving FORWARD
# makes its raw count DECREASE, on both sides.
COUNT_DIR_L = -1
COUNT_DIR_R = -1
# Full-scale track speed. Only sets how long the sim takes, not whether it converges.
MAX_TRACK_MPS = 0.45


class Robot:
    """True physical state plus the encoder counts the firmware would report."""

    def __init__(self, x=0.0, y=0.0, theta=0.0):
        self.x, self.y, self.theta = x, y, theta
        self.count_l = 100000
        self.count_r = -50000

    def step(self, throttle, turn, dt):
        left_pm, right_pm = stm32_mix(throttle, turn)
        dl = left_pm / 1000.0 * MAX_TRACK_MPS * dt
        dr = right_pm / 1000.0 * MAX_TRACK_MPS * dt
        ds = (dl + dr) / 2.0
        dtheta = (dr - dl) / TRACK_W
        self.theta = math.atan2(math.sin(self.theta + dtheta),
                                math.cos(self.theta + dtheta))
        self.x += ds * math.cos(self.theta)
        self.y += ds * math.sin(self.theta)
        self.count_l += dl / abs(SCALE_L) * COUNT_DIR_L
        self.count_r += dr / abs(SCALE_R) * COUNT_DIR_R


def make_follower(overrides=None):
    if overrides:
        merged = dict(BOOTSTRAP)
        merged['path_follower'] = dict(BOOTSTRAP['path_follower'], **overrides)
        rosstub.Node.PARAM_OVERRIDES = merged
    else:
        rosstub.Node.PARAM_OVERRIDES = BOOTSTRAP
    return path_follower.PathFollower()


def run_mission(plan, start_theta=None, max_seconds=180.0, turn_sign=-1.0,
                scale_sign=1.0):
    """Drive the real follower + real odometry + real firmware mixing to completion."""
    follower = make_follower()
    odom = odometry_node.OdometryNode()
    odom._left_scale = SCALE_L * scale_sign
    odom._right_scale = SCALE_R * scale_sign

    waypoints = plan['waypoints']
    if start_theta is None:
        start_theta = math.atan2(waypoints[1]['y'] - waypoints[0]['y'],
                                 waypoints[1]['x'] - waypoints[0]['x'])
    robot = Robot(theta=start_theta)

    drive = follower.publishers_by_topic['/silorobot/drive_command']
    pose_pub = odom.publishers_by_topic['/silorobot/pose']
    on_counts = odom.subscriptions_by_topic['/silorobot/wheel_counts']
    on_pose = follower.subscriptions_by_topic['/silorobot/pose']
    on_plan = follower.subscriptions_by_topic['/silorobot/plan']
    on_safety = follower.subscriptions_by_topic['/silorobot/safety_state']
    on_command = follower.subscriptions_by_topic['/silorobot/autonomy_command']

    # Seed odometry with a first sample so it has a baseline, then hand the pose over.
    counts = rosstub.Int32MultiArray([int(robot.count_l), int(robot.count_r)])
    on_counts(counts)
    odom._pose = {'x': robot.x, 'y': robot.y, 'theta': robot.theta}
    odom.timers[0][1]()
    on_pose(pose_pub.last())

    on_safety(rosstub.String(json.dumps({'state': 'NORMAL', 'armed': True})))
    on_plan(rosstub.String(json.dumps(plan)))
    on_command(rosstub.String(json.dumps({'type': 'route_start'})))

    dt = 1.0 / BOOTSTRAP['path_follower']['control_hz']
    ticks = int(max_seconds / dt)
    tick = follower.timers[0][1]
    trace = []
    for _ in range(ticks):
        CLOCK.advance(dt)
        # The deployed supervisor publishes its heartbeat continuously.  Reproduce that
        # contract so the follower's new stale-safety gate is exercised realistically.
        on_safety(rosstub.String(json.dumps({'state': 'NORMAL', 'armed': True})))
        tick()
        message = drive.last()
        throttle = message.linear.x if message else 0.0
        turn = message.angular.z if message else 0.0
        # turn_sign lets the harness re-break the convention on purpose to prove it notices.
        robot.step(throttle, turn * (-1.0 if turn_sign > 0 else 1.0), dt)
        on_counts(rosstub.Int32MultiArray([int(robot.count_l), int(robot.count_r)]))
        odom.timers[0][1]()
        on_pose(pose_pub.last())
        trace.append((robot.x, robot.y, robot.theta))
        if follower._state == 'COMPLETE':
            break
    return follower, robot, trace


print('=' * 72)
print('A-Z 검증 — 실제 배포 코드 구동 (재구현 아님)')
print('=' * 72)
print('설정 로드: bootstrap.yaml')
print('  scale L/R = {:+.9f} / {:+.9f}'.format(SCALE_L, SCALE_R))
print('  track_width = {} m,  encoder_alpha = {}'.format(
    TRACK_W, BOOTSTRAP['odometry_node']['encoder_alpha']))
print()

print('[1] coverage_planner — 계획 생성')
req = {'area': {'surface': 'RECTANGLE', 'width_m': 0.5, 'height_m': 0.5},
       'scan_width_m': 0.3, 'overlap_ratio': 0.2, 'safety_margin_m': 0.05,
       'start_corner': 'TOP_LEFT'}
plan = coverage_planner.make_plan(req)
wps = plan['waypoints']
check(len(wps) >= 2, '웨이포인트 생성됨', '{}개'.format(len(wps)))
inside = all(-1e-9 <= p['x'] <= 0.5 + 1e-9 and -1e-9 <= p['y'] <= 0.5 + 1e-9 for p in wps)
check(inside, '모든 웨이포인트가 영역 안')
margin_ok = all(p['x'] >= 0.05 - 1e-9 and p['y'] >= 0.05 - 1e-9 for p in wps)
check(margin_ok, '안전여백 침범 없음')
big = coverage_planner.make_plan(
    {'area': {'surface': 'RECTANGLE', 'width_m': 12.0, 'height_m': 8.0},
     'scan_width_m': 0.4, 'overlap_ratio': 0.2, 'safety_margin_m': 0.2})
check(len(big['waypoints']) == 50,
      '12x8m -> 50 웨이포인트 (간격 보장한 가로 25줄)',
      '{}개'.format(len(big['waypoints'])))
tall = coverage_planner.make_plan(
    {'area': {'surface': 'RECTANGLE', 'width_m': 12.0, 'height_m': 100.0},
     'scan_width_m': 0.4, 'overlap_ratio': 0.2, 'safety_margin_m': 0.2})
check(len(tall['waypoints']) == 76,
      '12x100m -> 76 웨이포인트 (간격 보장한 세로 38줄)',
      '{}개'.format(len(tall['waypoints'])))
for candidate in (plan, big, tall):
    cross_key = 'x' if candidate['orientation'] == 'VERTICAL' else 'y'
    lanes = sorted(set(round(point[cross_key], 9)
                       for point in candidate['waypoints']))
    requested_spacing = candidate['scan_width_m'] * (1.0 - candidate['overlap_ratio'])
    gaps = [right - left for left, right in zip(lanes, lanes[1:])]
    check(not gaps or max(gaps) <= requested_spacing + 1e-9,
          '{} 차선 간격이 요청값 이하'.format(candidate['orientation']),
          'max={:.3f}m requested={:.3f}m'.format(max(gaps) if gaps else 0.0,
                                                  requested_spacing))
print()

print('[2] STM32 실제 펌웨어 믹싱 (C 코드 직접 호출)')
fwd_l, fwd_r = stm32_mix(50, 0)
check(fwd_l > 0 and fwd_r > 0, '전진 명령 -> 좌우 모두 전진', '{} / {}'.format(fwd_l, fwd_r))
rt_l, rt_r = stm32_mix(0, 50)
check(rt_l > 0 and rt_r < 0, '우회전(turn>0) -> 좌 전진·우 후진 (사용자 증언과 일치)',
      '{} / {}'.format(rt_l, rt_r))
lt_l, lt_r = stm32_mix(0, -50)
check(lt_l < 0 and lt_r > 0, '좌회전(turn<0) -> 좌 후진·우 전진', '{} / {}'.format(lt_l, lt_r))
stop_l, stop_r = stm32_mix(0, 0)
check(stop_l == 0 and stop_r == 0, '정지 명령 -> 출력 0')
print()

print('[3] odometry_node — 부호 규약 (실제 코드)')
odom = odometry_node.OdometryNode()
on_counts = odom.subscriptions_by_topic['/silorobot/wheel_counts']
robot = Robot()
on_counts(rosstub.Int32MultiArray([int(robot.count_l), int(robot.count_r)]))
for _ in range(20):
    CLOCK.advance(0.05)
    robot.step(50, 0, 0.05)
    on_counts(rosstub.Int32MultiArray([int(robot.count_l), int(robot.count_r)]))
check(odom._pose['x'] > 0.01, '전진 -> 추정 x 증가', 'x={:+.3f}'.format(odom._pose['x']))
check(abs(odom._pose['theta']) < 0.05, '전진 -> 추정 theta 거의 불변',
      'theta={:+.4f}'.format(odom._pose['theta']))

odom2 = odometry_node.OdometryNode()
on_counts2 = odom2.subscriptions_by_topic['/silorobot/wheel_counts']
robot2 = Robot()
on_counts2(rosstub.Int32MultiArray([int(robot2.count_l), int(robot2.count_r)]))
for _ in range(20):
    CLOCK.advance(0.05)
    robot2.step(0, 50, 0.05)
    on_counts2(rosstub.Int32MultiArray([int(robot2.count_l), int(robot2.count_r)]))
check(odom2._pose['theta'] < -0.1, '우회전 -> 추정 theta 감소 (조향 부호 수정의 전제)',
      'theta={:+.3f}'.format(odom2._pose['theta']))
check(math.hypot(odom2._pose['x'], odom2._pose['y']) < 0.05,
      '제자리 회전 -> 이동거리 거의 0',
      'd={:.3f}m'.format(math.hypot(odom2._pose['x'], odom2._pose['y'])))
err = abs(odom2._pose['theta'] - robot2.theta)
check(err < 0.02, '추정 theta == 실제 theta (오도메트리 정확)',
      '오차 {:.4f} rad'.format(err))
print()

print('[4] path_follower — 계획/오도메트리 좌표계 정합 (anchor)')
follower = make_follower()
follower._plan = plan
follower._pose = {'x': 3.0, 'y': -2.0, 'theta': 1.1}
check(follower._set_anchor(), 'anchor 설정 성공')
ax, ay = follower._to_odom(wps[0])
check(abs(ax - 3.0) < 1e-9 and abs(ay + 2.0) < 1e-9,
      '첫 웨이포인트가 현재 위치에 고정됨', '({:.2f}, {:.2f})'.format(ax, ay))
bx, by = follower._to_odom(wps[1])
leg = math.atan2(by - ay, bx - ax)
check(abs(math.atan2(math.sin(leg - 1.1), math.cos(leg - 1.1))) < 1e-9,
      '첫 구간 방향이 로봇이 향한 방향과 일치')
px, py, pth = follower._to_plan(ax, ay, 1.1)
check(abs(px - wps[0]['x']) < 1e-9 and abs(py - wps[0]['y']) < 1e-9,
      '역변환 왕복 일치 (화면 마커용)')
print()

print('[5] 전체 폐루프 — 계획 -> 추종 -> 펌웨어 -> 물리 -> 엔코더 -> 오도메트리')
follower, robot, trace = run_mission(plan)
check(follower._state == 'COMPLETE', '미션 완주',
      'state={}, {}/{} 웨이포인트'.format(
          follower._state, follower._waypoint_index, len(wps)))
check(follower._waypoint_index >= len(wps), '모든 웨이포인트 도달')
travel = sum(math.hypot(trace[i][0] - trace[i - 1][0], trace[i][1] - trace[i - 1][1])
             for i in range(1, len(trace)))
check(travel < 6.0, '경로 길이가 합리적(빙빙 돌지 않음)', '{:.2f} m 주행'.format(travel))
print()

print('[6] 역검증 — 일부러 부호를 되돌리면 시험이 실패를 잡아내는가')
broken, _, _ = run_mission(plan, max_seconds=60.0, turn_sign=+1.0)
check(broken._state != 'COMPLETE', '조향 부호 뒤집으면 완주 실패 (= 어제까지의 증상)',
      'state={}, {}/{}'.format(broken._state, broken._waypoint_index, len(wps)))
broken2, _, _ = run_mission(plan, max_seconds=60.0, scale_sign=-1.0)
check(broken2._state != 'COMPLETE', '스케일 부호 뒤집으면 완주 실패',
      'state={}, {}/{}'.format(broken2._state, broken2._waypoint_index, len(wps)))
print()

print('[7] 시작 자세가 어긋나도 스스로 정렬하는가')
for offset_deg in (-90, -30, 30, 90, 150):
    base = math.atan2(wps[1]['y'] - wps[0]['y'], wps[1]['x'] - wps[0]['x'])
    f, _, _ = run_mission(plan, start_theta=base + math.radians(offset_deg))
    check(f._state == 'COMPLETE', '시작 각도 {:+4d}도에서 완주'.format(offset_deg),
          '{}/{}'.format(f._waypoint_index, len(wps)))
print()

print('[8] 큰 계획(12x8m, 50 웨이포인트)도 완주하는가')
f, _, trace = run_mission(big, max_seconds=3000.0)
check(f._state == 'COMPLETE', '대형 계획 완주',
      '{}/{} 웨이포인트'.format(f._waypoint_index, len(big['waypoints'])))
print()

print('=' * 72)
if FAILURES:
    print('결과: {}개 실패 / 총 {}개 검사'.format(len(FAILURES), CHECKS[0]))
    for name in FAILURES:
        print('   실패: ' + name)
    sys.exit(1)
print('결과: 전체 통과 ({}개 검사)'.format(CHECKS[0]))
