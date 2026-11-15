# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0

from silorobot_nano.calibration_report import distance_report
from silorobot_nano.calibration_report import odometry_report


def test_distance_report_prints_monotonic_luts(capsys):
    rows = []
    for target, values in ((20, (2581, 2583, 2579)),
                           (50, (1315, 1320, 1310)),
                           (150, (496, 500, 492))):
        for offset in (-2, 0, 2):
            rows.append({
                'target_mm': str(target),
                'adc_1': str(values[0] + offset),
                'adc_2': str(values[1] + offset),
                'adc_3': str(values[2] + offset),
            })
    distance_report(rows)
    output = capsys.readouterr().out
    assert 'targets_mm: [20, 50, 150]' in output
    assert '{2581u, 20u}' in output
    assert 'distance_3_points' in output


def test_odometry_report_calculates_scales(capsys):
    rows = [
        {'left_count': '100', 'right_count': '-200'},
        {'left_count': '-18460', 'right_count': '-18760'},
    ]
    odometry_report(rows, 1.0, None, None, None)
    output = capsys.readouterr().out
    assert 'meters_per_count_left=-0.000053879310' in output
    assert 'meters_per_count_right=-0.000053879310' in output
