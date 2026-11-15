"""Wire-protocol and safety-gate verification against the shipped source on both sides.

The Nano's framing/parsing is exercised as the real stm32_uart_bridge methods, and the
firmware's parser/builders are called in compiled C — so a mismatch between the two
implementations shows up here rather than on the bench.
"""

import ctypes
import importlib.util
import json
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

lib = ctypes.CDLL(os.path.join(HERE, LIBNAME))
lib.silo_parse_frame.argtypes = [
    ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int,
    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
lib.silo_make_telemetry.argtypes = [ctypes.c_int] * 4 + [ctypes.POINTER(ctypes.c_ubyte)]
lib.silo_make_encoder.argtypes = [ctypes.c_int] * 3 + [ctypes.POINTER(ctypes.c_ubyte)]
lib.silo_make_battery.argtypes = [ctypes.c_int] * 3 + [ctypes.POINTER(ctypes.c_ubyte)]

FAILURES = []
CHECKS = [0]


def check(condition, label, detail=''):
    CHECKS[0] += 1
    status = '[PASS]' if condition else '[FAIL]'
    print('  {} {}{}'.format(status, label, (' — ' + detail) if detail else ''))
    if not condition:
        FAILURES.append(label)


def load(name):
    spec = importlib.util.spec_from_file_location(
        'silo_' + name, os.path.join(PKG, name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def firmware_parse(payload):
    buf = (ctypes.c_ubyte * len(payload))(*payload)
    t, thr, turn = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
    ok = lib.silo_parse_frame(buf, len(payload),
                              ctypes.byref(t), ctypes.byref(thr), ctypes.byref(turn))
    return bool(ok), t.value, thr.value, turn.value


def firmware_telemetry(d1, d2, d3, flags):
    out = (ctypes.c_ubyte * 8)()
    n = lib.silo_make_telemetry(d1, d2, d3, flags, out)
    return bytes(out[:n])


def firmware_encoder(left, right, flags):
    out = (ctypes.c_ubyte * 13)()
    n = lib.silo_make_encoder(left, right, flags, out)
    return bytes(out[:n])


def firmware_battery(pack_1_mv, pack_2_mv, flags):
    out = (ctypes.c_ubyte * 9)()
    n = lib.silo_make_battery(pack_1_mv, pack_2_mv, flags, out)
    return bytes(out[:n])


stm32_uart_bridge = load('stm32_uart_bridge')
safety_supervisor = load('safety_supervisor')
dashboard_bridge = load('dashboard_bridge')

print('=' * 72)
print('통신 프로토콜 + 안전장치 검증 (양쪽 다 실제 코드)')
print('=' * 72)

print('[9] 하행 제어 프레임 — 나노가 만든 걸 STM32 펌웨어가 그대로 파싱하는가')
Bridge = stm32_uart_bridge.Stm32UartBridge
for name, cmd, thr, turn in [
        ('이동 +50/-30', stm32_uart_bridge.CMD_MOVE, 50, -30),
        ('이동 -100/+50 (볼트 기록 예제)', stm32_uart_bridge.CMD_MOVE, -100, 50),
        ('정지', stm32_uart_bridge.CMD_STOP, 0, 0),
        ('정지해제', stm32_uart_bridge.CMD_STOP_RELEASE, 0, 0),
        ('축값 -86 (바이트가 0xAA, 헤더와 같은 값)', stm32_uart_bridge.CMD_MOVE, -86, -86)]:
    frame = Bridge._make_command_frame(cmd, thr, turn)
    ok, ptype, pthr, pturn = firmware_parse(list(frame))
    matches = ok and ptype == cmd and pthr == thr and pturn == turn
    check(matches, '나노->STM32 {}'.format(name),
          '{} -> type={} thr={} turn={}'.format(frame.hex(), ptype, pthr, pturn))

known = Bridge._make_command_frame(stm32_uart_bridge.CMD_MOVE, -100, 50)
check(known.hex() == 'aa019c32af55', '볼트에 기록된 예제 프레임과 바이트 단위 일치',
      known.hex())

corrupt = bytearray(Bridge._make_command_frame(stm32_uart_bridge.CMD_MOVE, 50, -30))
corrupt[4] ^= 0xFF
ok, _, _, _ = firmware_parse(list(corrupt))
check(not ok, '체크섬 깨진 프레임은 펌웨어가 거부')

noisy = [0x00, 0xFF, 0x33] + list(Bridge._make_command_frame(
    stm32_uart_bridge.CMD_MOVE, 20, 10))
ok, _, thr, turn = firmware_parse(noisy)
check(ok and thr == 20 and turn == 10, '앞에 쓰레기 바이트가 섞여도 재동기화')

# The axes clamp to +-100, so the firmware's range guard should reject anything wider.
over = bytearray(Bridge._make_command_frame(stm32_uart_bridge.CMD_MOVE, 100, 100))
over[2] = 127
over[4] = over[1] ^ over[2] ^ over[3]
ok, _, _, _ = firmware_parse(list(over))
check(not ok, '범위 밖(+127) 축값은 펌웨어가 거부 (의도된 방어)')
check(Bridge._clamp_axis(500) == 100 and Bridge._clamp_axis(-500) == -100,
      '나노가 애초에 +-100으로 클램프해서 송신')

# 20 Hz back-to-back frames whose payload bytes are themselves 0xAA.
stream = bytearray()
for _ in range(5):
    stream += Bridge._make_command_frame(stm32_uart_bridge.CMD_MOVE, -86, -86)
ok, _, thr, turn = firmware_parse(list(stream))
check(ok and thr == -86 and turn == -86,
      '연속 프레임에서 페이로드의 0xAA를 헤더로 오인하지 않음')
print()

print('[10] 상행 텔레메트리 — STM32가 만든 걸 나노가 그대로 파싱하는가')
rosstub.Node.PARAM_OVERRIDES = {}
bridge = Bridge()
dist_pub = bridge.publishers_by_topic['/silorobot/distances_mm']
flags_pub = bridge.publishers_by_topic['/silorobot/stm32_flags']
wheel_pub = bridge.publishers_by_topic['/silorobot/wheel_counts']
encoder_flags_pub = bridge.publishers_by_topic['/silorobot/encoder_flags']
battery_pub = bridge.publishers_by_topic['/silorobot/battery_voltage']
battery_packs_pub = bridge.publishers_by_topic['/silorobot/battery_pack_mv']

bridge._receive_buffer.extend(firmware_telemetry(35, 72, 118, 0x01))
bridge._parse_telemetry_frames()
check(dist_pub.last() is not None and list(dist_pub.last().data) == [35, 72, 118],
      'STM32->나노 거리 프레임(0xBB) 값 일치',
      str(list(dist_pub.last().data)) if dist_pub.last() else 'none')
check(flags_pub.last() is not None and flags_pub.last().data == 0x01,
      '상태 flags 전달')

bridge._receive_buffer.extend(firmware_encoder(-1234567, 890123, 0x03))
bridge._parse_telemetry_frames()
counts = wheel_pub.last()
check(counts is not None and list(counts.data) == [-1234567, 890123],
      'STM32->나노 엔코더 프레임(0xBC) 음수 포함 정확 복원',
      str(list(counts.data)) if counts else 'none')
check(encoder_flags_pub.last() is not None and encoder_flags_pub.last().data == 0x03,
      '엔코더 로컬 flags를 별도 토픽으로 보존')

bridge._receive_buffer.extend(firmware_battery(11120, 10980, 0x03))
bridge._parse_telemetry_frames()
packs = battery_packs_pub.last()
check(packs is not None and list(packs.data) == [11120, 10980],
      'STM32->나노 배터리 0xBE 두 팩 mV 복원')
check(battery_pub.last() is not None and abs(battery_pub.last().data - 10.98) < 1e-6,
      '대표 배터리 전압은 유효한 두 팩 중 낮은 값')

# Both frame types arriving back to back inside one read, plus leading noise.
bridge2 = Bridge()
mixed = bytearray([0x11, 0x22])
mixed += firmware_telemetry(10, 20, 30, 0)
mixed += firmware_encoder(7, -9, 0x03)
mixed += firmware_battery(12000, 11900, 0x03)
bridge2._receive_buffer.extend(mixed)
bridge2._parse_telemetry_frames()
d = bridge2.publishers_by_topic['/silorobot/distances_mm'].last()
w = bridge2.publishers_by_topic['/silorobot/wheel_counts'].last()
b = bridge2.publishers_by_topic['/silorobot/battery_voltage'].last()
check(d is not None and list(d.data) == [10, 20, 30] and
      w is not None and list(w.data) == [7, -9] and
      b is not None and abs(b.data - 11.9) < 1e-6,
      '혼합 프레임 + 잡음을 한 번에 정확히 분리')

# Split reads: the firmware's bytes trickle in one at a time.
bridge3 = Bridge()
for byte in firmware_encoder(555, -666, 0x03):
    bridge3._receive_buffer.append(byte)
    bridge3._parse_telemetry_frames()
w3 = bridge3.publishers_by_topic['/silorobot/wheel_counts'].last()
check(w3 is not None and list(w3.data) == [555, -666],
      '1바이트씩 쪼개져 들어와도 복원')
print()

print('[11] safety_supervisor — 정지/해제 게이트 (실제 코드)')

check(dashboard_bridge.DashboardBridge._default_safety_state()['latched'],
      '안전상태 첫 수신 전 대시보드 브릿지는 정지 래치로 시작')


class Clock:
    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


clock = Clock()
safety_supervisor.time = clock
rosstub.Node.PARAM_OVERRIDES = {'safety_supervisor': {
    'armed': False, 'stale_ms': 300, 'startup_grace_ms': 0, 'release_stable_ms': 500,
    'distance_spread_warn_mm': 15.0, 'distance_spread_stop_mm': 30.0,
    'distance_rate_stop_mm_s': 120.0, 'omega_warn_dps': 60.0, 'omega_stop_dps': 120.0,
    'accel_deviation_g': 0.35, 'battery_release_mv': 10200,
    'distance_calibration_confirmed': False,
    'require_distance': False}}

sup = safety_supervisor.SafetySupervisor()
stop_pub = sup.publishers_by_topic['/silorobot/emergency_stop']
state_pub = sup.publishers_by_topic['/silorobot/safety_state']
tick = sup.timers[0][1]
on_flags = sup.subscriptions_by_topic['/silorobot/stm32_flags']
on_conn = sup.subscriptions_by_topic['/silorobot/stm32_connected']
on_stop = sup.subscriptions_by_topic['/silorobot/stop_request']
on_battery_packs = sup.subscriptions_by_topic['/silorobot/battery_pack_mv']
on_battery_flags = sup.subscriptions_by_topic['/silorobot/battery_flags']

tick()
check(json.loads(state_pub.last().data)['latched'],
      '부팅 직후 정지 래치 (안전 기본값)')

on_conn(rosstub.Bool(True))
on_flags(rosstub.UInt8(0x01))   # STM32 reports its own stop latch
tick()
on_stop(rosstub.Bool(False))    # operator asks for release
clock.advance(0.1)
tick()
state = json.loads(state_pub.last().data)
check(state['latched'], '안정화 시간 전에는 해제 안 됨(500ms 요구)',
      'reasons={}'.format(state['reasons']))

for _ in range(10):
    clock.advance(0.1)
    on_flags(rosstub.UInt8(0x01))
    tick()
on_stop(rosstub.Bool(False))
clock.advance(0.1)
tick()
released_state = json.loads(state_pub.last().data)
released = not released_state['latched']
check(released and not released_state['imu_meta']['valid'],
      '거리센서·IMU가 없어도 명시적 데모모드는 해제됨')
check(stop_pub.last() is not None and stop_pub.last().data is False,
      '해제 시 emergency_stop=false 펄스 발행')

on_stop(rosstub.Bool(True))
tick()
check(json.loads(state_pub.last().data)['latched'], '정지 요청은 즉시 래치')
check(stop_pub.last().data is True, '정지 시 emergency_stop=true 유지')

on_battery_packs(rosstub.UInt16MultiArray([9800, 10100]))
on_battery_flags(rosstub.UInt8(0x1f))
tick()
battery_state = json.loads(state_pub.last().data)
check('battery_warning' in battery_state['reasons'] and
      'battery_stop_latched' in battery_state['reasons'],
      '저전압 경고/정지 래치를 안전 상태에 보존')
check(battery_state['battery_meta']['packs_mv'] == [9800, 10100],
      '배터리 두 팩 실측값을 안전 상태에 보존')
distance = battery_state['distance_meta']
imu = battery_state['imu_meta']
check(not sup._release_allowed(distance, imu),
      '저전압 정지 래치는 현재 전압이 낮으면 해제 거부')
on_battery_packs(rosstub.UInt16MultiArray([10300, 10400]))
check(sup._release_allowed(distance, imu),
      '두 팩 회복 후 과거 저전압 래치가 있어도 해제 명령 허용')

# Distance required (the real field configuration) must refuse release while uncalibrated.
rosstub.Node.PARAM_OVERRIDES['safety_supervisor']['require_distance'] = True
sup2 = safety_supervisor.SafetySupervisor()
tick2 = sup2.timers[0][1]
sup2.subscriptions_by_topic['/silorobot/stm32_connected'](rosstub.Bool(True))
for _ in range(15):
    clock.advance(0.1)
    sup2.subscriptions_by_topic['/silorobot/stm32_flags'](rosstub.UInt8(0x01))
    sup2.subscriptions_by_topic['/silorobot/stop_request'](rosstub.Bool(False))
    tick2()
still_latched = json.loads(
    sup2.publishers_by_topic['/silorobot/safety_state'].last().data)['latched']
check(still_latched,
      '거리센서 필수 모드에서는 미보정 상태 해제 거부 (현장 기본값)')
print()

print('=' * 72)
if FAILURES:
    print('결과: {}개 실패 / 총 {}개 검사'.format(len(FAILURES), CHECKS[0]))
    for name in FAILURES:
        print('   실패: ' + name)
    sys.exit(1)
print('결과: 전체 통과 ({}개 검사)'.format(CHECKS[0]))
