#!/usr/bin/env python3
# Copyright 2026 SiloRobot
# Licensed under the Apache License, Version 2.0
"""CSI camera RTSP server for the SiloRobot Nano B01."""

import threading

import gi

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')

from gi.repository import GLib, Gst, GstRtspServer  # noqa: E402
import rclpy  # noqa: E402
from rclpy.node import Node  # noqa: E402


DEFAULT_RTSP_PORT = 8554
DEFAULT_MOUNT_POINT = '/robot'


class CameraRtspServer(Node):
    """Serve the Nano CSI camera as H.264 RTSP without re-encoding on CPU."""

    def __init__(self):
        super().__init__('camera_rtsp_server')

        self.declare_parameter('port', DEFAULT_RTSP_PORT)
        self.declare_parameter('mount_point', DEFAULT_MOUNT_POINT)
        self.declare_parameter('width', 1280)
        self.declare_parameter('height', 720)
        self.declare_parameter('framerate', 30)
        self.declare_parameter('bitrate', 4000000)
        self.declare_parameter('advertise_host', '100.121.144.38')

        self._port = self.get_parameter('port').value
        self._mount_point = self.get_parameter('mount_point').value
        self._width = self.get_parameter('width').value
        self._height = self.get_parameter('height').value
        self._framerate = self.get_parameter('framerate').value
        self._bitrate = self.get_parameter('bitrate').value
        self._advertise_host = self.get_parameter('advertise_host').value

        Gst.init(None)
        self._main_loop = GLib.MainLoop()
        self._server = GstRtspServer.RTSPServer.new()
        self._server.set_service(str(self._port))

        factory = GstRtspServer.RTSPMediaFactory.new()
        factory.set_shared(True)
        factory.set_launch(self._pipeline())
        self._server.get_mount_points().add_factory(self._mount_point, factory)

        if self._server.attach(None) == 0:
            raise RuntimeError('Unable to attach the RTSP server to GLib')

        self._glib_thread = threading.Thread(
            target=self._main_loop.run,
            name='camera-rtsp-glib',
            daemon=True)
        self._glib_thread.start()

        self.get_logger().info(
            'RTSP ready: rtsp://{}:{}{}'.format(
                self._advertise_host, self._port, self._mount_point))

    def _pipeline(self):
        caps = (
            'video/x-raw(memory:NVMM),width={width},height={height},'
            'framerate={framerate}/1,format=NV12').format(
                width=self._width,
                height=self._height,
                framerate=self._framerate)
        return (
            '( nvarguscamerasrc ! {caps} ! '
            'nvv4l2h264enc bitrate={bitrate} insert-sps-pps=true '
            'iframeinterval={framerate} ! h264parse ! '
            'rtph264pay name=pay0 pt=96 config-interval=1 )').format(
                caps=caps,
                bitrate=self._bitrate,
                framerate=self._framerate)

    def destroy_node(self):
        if self._main_loop.is_running():
            self._main_loop.quit()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CameraRtspServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
