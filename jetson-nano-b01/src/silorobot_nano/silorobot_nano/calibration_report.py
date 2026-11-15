#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""Calculate distance LUT and odometry recommendations from collector CSV."""

import argparse
import csv
import pathlib
import statistics


def load_rows(path):
    with pathlib.Path(path).open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def distance_report(rows):
    grouped = {}
    for row in rows:
        if not row.get('target_mm'):
            continue
        target = int(row['target_mm'])
        grouped.setdefault(target, [[], [], []])
        for index, key in enumerate(('adc_1', 'adc_2', 'adc_3')):
            if row.get(key):
                grouped[target][index].append(int(row[key]))
    if len(grouped) < 2:
        raise SystemExit('distance report needs at least two target-mm groups')
    targets = sorted(grouped)
    medians = [[round(statistics.median(grouped[target][index]))
                for target in targets] for index in range(3)]
    for values in medians:
        if any(values[i] <= values[i + 1] for i in range(len(values) - 1)):
            raise SystemExit(
                'ADC medians must decrease as distance increases; '
                'check target labels/wiring')
    print('targets_mm:', targets)
    for index, values in enumerate(medians, 1):
        pairs = ', '.join('{{{}u, {}u}}'.format(adc, mm)
                          for adc, mm in zip(values, targets))
        print('distance_{}_points = {{ {} }};'.format(index, pairs))


def odometry_report(rows, distance_m, turn_radians, left_scale, right_scale):
    valid = [row for row in rows if row.get('left_count') and row.get('right_count')]
    if len(valid) < 2:
        raise SystemExit('odometry report needs at least two wheel-count samples')
    dl_count = int(valid[-1]['left_count']) - int(valid[0]['left_count'])
    dr_count = int(valid[-1]['right_count']) - int(valid[0]['right_count'])
    print('delta_counts: left={} right={}'.format(dl_count, dr_count))
    if distance_m is not None:
        if dl_count == 0 or dr_count == 0:
            raise SystemExit('wheel count delta is zero')
        if dl_count * dr_count < 0:
            raise SystemExit(
                'straight-run wheel counts have opposite signs; check encoder wiring/signs')
        # Preserve the observed encoder direction.  On the assembled SiloRobot both raw
        # counts decrease during forward travel, so the correct scales are both negative.
        # Using abs(count) here used to print plausible-looking positive values that made
        # odometry run backwards as soon as the recommended values were pasted into YAML.
        print('meters_per_count_left={:.12f}'.format(distance_m / dl_count))
        print('meters_per_count_right={:.12f}'.format(distance_m / dr_count))
    if turn_radians is not None:
        if left_scale is None or right_scale is None:
            raise SystemExit('--turn-radians requires --left-scale and --right-scale')
        track = abs(dr_count * right_scale - dl_count * left_scale) / abs(turn_radians)
        print('track_width_m={:.6f}'.format(track))


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_file')
    parser.add_argument('--distance-lut', action='store_true')
    parser.add_argument('--distance-m', type=float)
    parser.add_argument('--turn-radians', type=float)
    parser.add_argument('--left-scale', type=float)
    parser.add_argument('--right-scale', type=float)
    parsed = parser.parse_args(args)
    rows = load_rows(parsed.csv_file)
    if not rows:
        raise SystemExit('CSV is empty')
    if parsed.distance_lut:
        distance_report(rows)
    if parsed.distance_m is not None or parsed.turn_radians is not None:
        odometry_report(rows, parsed.distance_m, parsed.turn_radians,
                        parsed.left_scale, parsed.right_scale)
    if not parsed.distance_lut and parsed.distance_m is None and parsed.turn_radians is None:
        raise SystemExit('select --distance-lut, --distance-m, or --turn-radians')


if __name__ == '__main__':
    main()
