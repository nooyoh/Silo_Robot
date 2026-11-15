# SiloRobot RPi4 Dashboard

Raspberry Pi 4 + 7-inch touchscreen dashboard for the SiloRobot crawler.

## Features

- Qt 6 Quick touch UI for a landscape 800×480 display
- RTSP video display from Jetson Nano B01 (`720p @ 30fps` target)
- WebSocket server on port `8765`
- Touch controls: throttle and turn axes (`-100` to `100`), latched emergency stop
- Robot telemetry (battery, IMU, three distance sensors)
- Orin Nano defect boxes rendered over the video without re-encoding the stream
- Persistent connection configuration: dashboard address, RTSP URL, and WebSocket port
- Matte industrial operator-console visual system: Korean action text, restrained safety colors,
  linear touch axes, and a dedicated emergency-stop control
- Handheld layout: lower-left throttle and lower-right steering zones support two-thumb operation
  while holding the 7-inch display case
- `--demo` mode for UI-only verification before other devices are ready; it never fabricates a
  defect alert

## Build on Raspberry Pi

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
./build/silorobot-dashboard --demo
```

Run with the Nano B01 RTSP source once it is available:

```bash
./build/silorobot-dashboard --rtsp rtsp://<nano-tailscale-ip>:8554/robot
```

## Connection configuration

Use the top-right **연결 설정** control in the UI to save the dashboard Tailscale address,
camera RTSP URL, and WebSocket port. Values are stored in Qt `QSettings`
(`SiloRobot/Dashboard`) and are reused on the next launch. The shown
`ws://<address>:<port>` value is the endpoint that Nano B01 and Orin should use.

The configuration popup is deliberately wide (760×470 at the 800×480 target resolution) and
includes its own touch URL keyboard. It supports lowercase letters, digits, `.`, `:`, `/`, `-`,
`_`, `@`, space, backspace, and done, so no physical keyboard is needed in the field.

The dashboard listens on every local interface; changing the displayed address does not bind
the server to a different network interface. It also does not remotely rewrite the clients'
own connection settings.

Korean UI labels require a Korean-capable font. The current RPi user has Noto Sans CJK KR in
`~/.local/share/fonts`; install `fonts-noto-cjk` (system-wide or user-local) on a fresh image.

## WebSocket contract

The dashboard listens on all interfaces at port `8765`. Nano B01 and Orin Nano Super connect as clients.

Nano B01 sends at 10 Hz:

```json
{"type":"status","battery":11.8,"imu":{"roll":0.3,"pitch":-1.1,"yaw":87.4},"distance":[78,80,79],"connected":true}
```

The dashboard sends to Nano B01:

```json
{"type":"move","throttle":-100,"turn":50}
{"type":"stop"}
{"type":"stop_release"}
```

Orin Nano Super sends a normalized (`0.0`–`1.0`) bounding-box list:

```json
{"type":"detection","detections":[{"x":0.59,"y":0.35,"width":0.16,"height":0.20,"label":"crack","confidence":0.93}]}
```

`hello` messages with `role: "nano"` or `role: "orin"` are optional but recommended. The dashboard also identifies clients from `status` and `detection` messages.
