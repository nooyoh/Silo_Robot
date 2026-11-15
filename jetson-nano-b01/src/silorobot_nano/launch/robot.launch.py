"""
Bring up every Nano B01 robot-brain process with safe defaults.

The safety supervisor is deliberately unarmed by default. Odometry uses a
clearly documented bootstrap profile that launch arguments can override.
"""

# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():
    dashboard_uri = LaunchConfiguration('dashboard_uri')
    stm_port = LaunchConfiguration('stm_port')
    imu_port = LaunchConfiguration('imu_port')
    use_camera = LaunchConfiguration('use_camera')
    armed = LaunchConfiguration('armed')
    distance_calibration_confirmed = LaunchConfiguration('distance_calibration_confirmed')
    require_distance = LaunchConfiguration('require_distance')
    allow_unarmed_autonomy = LaunchConfiguration('allow_unarmed_autonomy')
    demo_square = LaunchConfiguration('demo_square')
    demo_square_size_m = LaunchConfiguration('demo_square_size_m')
    demo_square_side_seconds = LaunchConfiguration('demo_square_side_seconds')
    demo_square_turn_seconds = LaunchConfiguration('demo_square_turn_seconds')
    demo_square_straight_command = LaunchConfiguration(
        'demo_square_straight_command')
    demo_square_turn_command = LaunchConfiguration('demo_square_turn_command')
    profile_file = LaunchConfiguration('profile_file')

    arguments = [
        DeclareLaunchArgument('dashboard_uri', default_value='ws://100.74.141.112:8765'),
        DeclareLaunchArgument('stm_port', default_value='/dev/ttyACM0'),
        DeclareLaunchArgument('imu_port', default_value='/dev/ttyTHS1'),
        DeclareLaunchArgument('use_camera', default_value='true'),
        DeclareLaunchArgument('armed', default_value='false'),
        DeclareLaunchArgument('distance_calibration_confirmed', default_value='false'),
        # Distance sensors are not mounted yet during drivetrain bench testing. Set to false
        # only for that bench phase; put it back to true (the default) once sensors are wired —
        # do not confuse this with distance_calibration_confirmed, which is a separate gate.
        DeclareLaunchArgument('require_distance', default_value='true'),
        # Keep false in normal operation.  Set true only for restrained HIL/bench testing
        # where the robot cannot translate or fall and distance sensors are not mounted.
        DeclareLaunchArgument('allow_unarmed_autonomy', default_value='false'),
        DeclareLaunchArgument('demo_square', default_value='false'),
        DeclareLaunchArgument('demo_square_size_m', default_value='0.5'),
        DeclareLaunchArgument('demo_square_side_seconds', default_value='1.5'),
        DeclareLaunchArgument('demo_square_turn_seconds', default_value='0.6'),
        DeclareLaunchArgument('demo_square_straight_command', default_value='50.0'),
        DeclareLaunchArgument('demo_square_turn_command', default_value='40.0'),
        DeclareLaunchArgument(
            'profile_file',
            default_value=PathJoinSubstitution([
                FindPackageShare('silorobot_nano'), 'config', 'bootstrap.yaml'])),
    ]
    common = {'package': 'silorobot_nano', 'output': 'screen'}
    nodes = [
        Node(node_executable='dashboard_bridge', node_name='dashboard_bridge',
             parameters=[{'dashboard_uri': dashboard_uri}], **common),
        Node(node_executable='stm32_uart_bridge', node_name='stm32_uart_bridge',
             parameters=[{'port': stm_port}], **common),
        Node(node_executable='imu_node', node_name='imu_node',
             parameters=[{'port': imu_port}], **common),
        Node(node_executable='safety_supervisor', node_name='safety_supervisor',
             parameters=[profile_file, {
                 'armed': armed,
                 'distance_calibration_confirmed': distance_calibration_confirmed,
                 'require_distance': require_distance}], **common),
        Node(node_executable='odometry_node', node_name='odometry_node',
             parameters=[profile_file], **common),
        Node(node_executable='coverage_planner', node_name='coverage_planner',
             condition=UnlessCondition(demo_square), **common),
        Node(node_executable='path_follower', node_name='path_follower',
             condition=UnlessCondition(demo_square),
             parameters=[profile_file, {
                 'allow_unarmed_autonomy': allow_unarmed_autonomy}], **common),
        Node(node_executable='demo_square', node_name='demo_square',
             condition=IfCondition(demo_square), parameters=[{
                 'square_size_m': demo_square_size_m,
                 'side_seconds': demo_square_side_seconds,
                 'turn_seconds': demo_square_turn_seconds,
                 'straight_command': demo_square_straight_command,
                 'turn_command': demo_square_turn_command}], **common),
        Node(node_executable='camera_rtsp_server', node_name='camera_rtsp_server',
             condition=IfCondition(use_camera), **common),
    ]
    return LaunchDescription(arguments + nodes)
