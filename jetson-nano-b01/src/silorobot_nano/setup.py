import os
from glob import glob

from setuptools import setup

package_name = 'silorobot_nano'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
         glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools', 'pyserial', 'websockets'],
    zip_safe=True,
    maintainer='jetson',
    maintainer_email='jetson@todo.todo',
    description='ROS 2 hardware, safety, dashboard, and low-speed autonomy nodes for SiloRobot',
    license='Proprietary',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'dashboard_bridge = silorobot_nano.dashboard_bridge:main',
            'camera_rtsp_server = silorobot_nano.camera_rtsp_server:main',
            'stm32_uart_bridge = silorobot_nano.stm32_uart_bridge:main',
            'imu_node = silorobot_nano.imu_node:main',
            'safety_supervisor = silorobot_nano.safety_supervisor:main',
            'odometry_node = silorobot_nano.odometry_node:main',
            'coverage_planner = silorobot_nano.coverage_planner:main',
            'path_follower = silorobot_nano.path_follower:main',
            'demo_square = silorobot_nano.demo_square:main',
            'calibration_collector = silorobot_nano.calibration_collector:main',
            'calibration_report = silorobot_nano.calibration_report:main',
            'watch_wheels = silorobot_nano.watch_wheels:main',
            'watch_gyro = silorobot_nano.watch_gyro:main',
            'verify_signs = silorobot_nano.verify_signs:main',
        ],
    },
)
