#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""Build the firmware bridge and run the whole off-robot verification suite.

    python3 tools/verify/run.py

Needs only a C compiler and Python 3 - no ROS, no hardware. Point --stm32 at the
firmware checkout if it is not the sibling directory the layout assumes.
"""

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_STM32 = os.path.join(os.path.dirname(REPO), 'stm32-controller')
LIBNAME = 'silofw.dll' if sys.platform == 'win32' else 'libsilofw.so'

SOURCES = ['silo_controller.c', 'silo_motor_driver.c', 'silo_protocol.c']


def build_bridge(stm32_dir):
    """Compile the real firmware sources into a shared library the tests can call."""
    app = os.path.join(stm32_dir, 'App')
    missing = [name for name in SOURCES
               if not os.path.exists(os.path.join(app, 'Src', name))]
    if missing:
        raise SystemExit(
            'firmware sources not found in {} (missing {}). '
            'Pass --stm32 <path to stm32-controller>.'.format(app, ', '.join(missing)))
    command = ['gcc', '-std=c11', '-Wall', '-Wextra', '-shared', '-fPIC',
               '-I', os.path.join(app, 'Inc'),
               '-o', os.path.join(HERE, LIBNAME),
               os.path.join(HERE, 'firmware_bridge.c')]
    command += [os.path.join(app, 'Src', name) for name in SOURCES]
    subprocess.run(command, check=True)


def run_firmware_unit_tests(stm32_dir):
    """Run the firmware's own C test binary, if the checkout has it."""
    test_main = os.path.join(stm32_dir, 'tests', 'test_main.c')
    if not os.path.exists(test_main):
        print('  (건너뜀: {} 없음)'.format(test_main), flush=True)
        return True
    app = os.path.join(stm32_dir, 'App')
    binary = os.path.join(HERE, 'stm32_tests.exe' if sys.platform == 'win32'
                          else 'stm32_tests')
    sources = ['silo_protocol.c', 'silo_controller.c', 'silo_motor_driver.c',
               'silo_distance.c', 'silo_encoder.c', 'silo_battery.c']
    subprocess.run(
        ['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror',
         '-DSILO_BATTERY_MONITOR_ENABLED=1',
         '-I', os.path.join(app, 'Inc'), '-o', binary, test_main]
        + [os.path.join(app, 'Src', name) for name in sources], check=True)
    return subprocess.run([binary]).returncode == 0


def main():
    # Keep Korean diagnostics readable in Windows terminals and captured CI logs.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stm32', default=DEFAULT_STM32,
                        help='path to the stm32-controller checkout')
    args = parser.parse_args()

    print('=' * 72, flush=True)
    print('SiloRobot 오프로봇 검증 - 실제 배포 코드 구동', flush=True)
    print('=' * 72, flush=True)

    build_bridge(args.stm32)

    failed = []
    print('\n########## 1/4  STM32 펌웨어 단위시험 (실제 C) ##########', flush=True)
    if not run_firmware_unit_tests(args.stm32):
        failed.append('STM32 단위시험')

    environment = dict(os.environ, PYTHONIOENCODING='utf-8')
    for label, script in [('2/4  자율주행 폐루프', 'test_autonomy_loop.py'),
                          ('3/4  통신 프로토콜 + 안전장치', 'test_wire_protocol.py'),
                          ('4/4  영상용 하드코딩 사각 경로', 'test_demo_square.py')]:
        print('\n########## {} ##########'.format(label), flush=True)
        result = subprocess.run([sys.executable, os.path.join(HERE, script)],
                                env=environment)
        if result.returncode != 0:
            failed.append(label)

    print('\n' + '=' * 72)
    if failed:
        print('실패: ' + ', '.join(failed))
        return 1
    print('전체 통과')
    return 0


if __name__ == '__main__':
    sys.exit(main())
