#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""Pure coverage-plan generation for a rectangular silo development."""

import datetime
import json
import math

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def _as_positive(data, key):
    value = float(data[key])
    if not math.isfinite(value) or value <= 0:
        raise ValueError('{} must be positive'.format(key))
    return value


def _line_positions(length, margin, spacing):
    usable = length - 2.0 * margin
    if usable <= 0:
        raise ValueError('margin leaves no inspectable area')
    # One centred pass is sufficient only when its effective scan width covers
    # the whole usable span.  Otherwise ``ceil(usable / spacing)`` is the number
    # of *intervals*, not the number of lane centres.  The previous code omitted
    # the final centre, so an exact 1.0 m / 0.2 m request produced four intervals
    # of 0.25 m and left uninspected strips between passes.
    if usable <= spacing:
        return [margin + usable / 2.0]
    count = int(math.ceil(usable / spacing)) + 1
    return [margin + usable * index / (count - 1) for index in range(count)]


def _candidate(width, height, margin, spacing, vertical, start_corner, turn_cost):
    cross = width if vertical else height
    along = height if vertical else width
    positions = _line_positions(cross, margin, spacing)
    low, high = margin, along - margin
    reverse_cross = start_corner.endswith('RIGHT') if vertical else start_corner.startswith('TOP')
    reverse_along = start_corner.startswith('TOP') if vertical else start_corner.endswith('RIGHT')
    if reverse_cross:
        positions.reverse()
    points = []
    for index, cross_value in enumerate(positions):
        endpoints = (high, low) if (index % 2 == 0) == reverse_along else (low, high)
        for along_value in endpoints:
            points.append({'x': cross_value, 'y': along_value} if vertical else
                          {'x': along_value, 'y': cross_value})
    length = max(0, len(positions)) * (along - 2.0 * margin)
    for index in range(1, len(points), 2):
        if index + 1 < len(points):
            length += math.hypot(points[index + 1]['x'] - points[index]['x'],
                                 points[index + 1]['y'] - points[index]['y'])
    turn_count = max(0, len(positions) - 1)
    return {'orientation': 'VERTICAL' if vertical else 'HORIZONTAL',
            'estimated_length_m': length, 'turn_count': turn_count,
            'estimated_cost': length + turn_count * turn_cost,
            'waypoints': points}


def make_plan(request, plan_id=None):
    area = request.get('area', {})
    surface = area.get('surface', 'RECTANGLE')
    height = _as_positive(area, 'height_m')
    if surface == 'RECTANGLE':
        width = _as_positive(area, 'width_m')
    elif surface == 'CYLINDER_SIDE':
        width = math.pi * _as_positive(area, 'diameter_m')
    else:
        raise ValueError('surface must be RECTANGLE or CYLINDER_SIDE')
    scan_width = _as_positive(request, 'scan_width_m')
    overlap = float(request.get('overlap_ratio', 0.0))
    margin = float(request.get('safety_margin_m', 0.0))
    # Equivalent travel cost of one in-place 180-degree lane change.  0.5 m is a
    # conservative theory default for the slow tracked chassis and prevents a very tall
    # area from choosing hundreds of short horizontal passes merely to save a few metres.
    turn_cost = float(request.get('turn_cost_m', 0.5))
    if not 0 <= overlap < 1 or margin < 0 or turn_cost < 0:
        raise ValueError('invalid overlap, safety_margin_m, or turn_cost_m')
    spacing = scan_width * (1.0 - overlap)
    start_corner = request.get('start_corner', 'BOTTOM_LEFT')
    if start_corner not in ('BOTTOM_LEFT', 'BOTTOM_RIGHT', 'TOP_LEFT', 'TOP_RIGHT'):
        raise ValueError('invalid start_corner')
    vertical = _candidate(
        width, height, margin, spacing, True, start_corner, turn_cost)
    horizontal = _candidate(
        width, height, margin, spacing, False, start_corner, turn_cost)
    chosen = min(
        (vertical, horizontal),
        key=lambda item: (item['estimated_cost'], item['estimated_length_m']))
    return {
        'type': 'route_plan',
        'plan_id': plan_id or datetime.datetime.utcnow().strftime(
            '%Y%m%d-%H%M%S-%f')[:-3],
        'planner': 'RECTANGULAR_BOUSTROPHEDON_V1',
        'surface': surface, 'width_m': width, 'height_m': height,
        'scan_width_m': scan_width, 'overlap_ratio': overlap,
        'safety_margin_m': margin, 'turn_cost_m': turn_cost,
        'start_corner': start_corner,
        'orientation': chosen['orientation'],
        'estimated_length_m': round(chosen['estimated_length_m'], 4),
        'estimated_cost': round(chosen['estimated_cost'], 4),
        'turn_count': chosen['turn_count'], 'waypoints': chosen['waypoints'],
        'candidates': [{key: item[key] for key in (
            'orientation', 'estimated_length_m', 'turn_count', 'estimated_cost')}
                       for item in (vertical, horizontal)],
    }


class CoveragePlanner(Node):
    def __init__(self):
        super().__init__('coverage_planner')
        self._publisher = self.create_publisher(String, '/silorobot/plan', 10)
        self.create_subscription(String, '/silorobot/route_plan_request', self._on_request, 10)

    def _on_request(self, message):
        try:
            request = json.loads(message.data)
            plan = make_plan(request)
        except (TypeError, ValueError, KeyError) as error:
            self.get_logger().warn('Rejected route plan request: {}'.format(error))
            return
        self._publisher.publish(String(data=json.dumps(plan, allow_nan=False)))


def main(args=None):
    rclpy.init(args=args)
    node = CoveragePlanner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
