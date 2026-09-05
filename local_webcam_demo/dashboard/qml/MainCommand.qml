import QtQuick
import QtQuick.Controls
import QtMultimedia

ApplicationWindow {
    id: window
    visible: true
    width: 800
    height: 480
    minimumWidth: 800
    minimumHeight: 480
    title: "SiloRobot Command Console"
    color: "#101214"

    property int throttle: 0
    property int turn: 0
    property bool emergencyLatched: false
    property int leftMotor: Math.max(-100, Math.min(100, throttle + turn))
    property int rightMotor: Math.max(-100, Math.min(100, throttle - turn))

    function sendMotion() {
        if (!emergencyLatched)
            dashboard.sendMove(throttle, turn)
    }

    Timer {
        interval: 50
        running: !window.emergencyLatched && (driveGauge.held || turnGauge.held)
        repeat: true
        onTriggered: window.sendMotion()
    }

    Rectangle {
        anchors.fill: parent
        color: "#101214"
    }

    Repeater {
        model: 28
        Rectangle {
            x: index * 30
            y: 0
            width: 1
            height: parent.height
            color: "#151A1D"
        }
    }

    Rectangle {
        id: systemBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 34
        color: "#171B1E"
        border.color: "#373F43"
        border.width: 1

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 13
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            Rectangle { width: 6; height: 6; color: dashboard.robotOnline ? "#65D6A2" : "#5B656A" }
            Text {
                text: "SAILOBOT"
                color: "#ECF0F0"
                font.family: "DejaVu Sans Mono"
                font.pixelSize: 13
                font.bold: true
                font.letterSpacing: 1.6
            }
            Text {
                text: "/  INSPECTION COMMAND"
                color: "#91A0A4"
                font.family: "DejaVu Sans Mono"
                font.pixelSize: 9
                font.bold: true
            }
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 13
            anchors.verticalCenter: parent.verticalCenter
            spacing: 11
            Text { text: "MODE: MANUAL"; color: "#D4DEDF"; font.family: "DejaVu Sans Mono"; font.pixelSize: 9; font.bold: true }
            Rectangle { width: 1; height: 14; color: "#495358" }
            Text { text: dashboard.robotOnline ? "LINK: NOMINAL" : "LINK: WAIT"; color: dashboard.robotOnline ? "#65D6A2" : "#D3A455"; font.family: "DejaVu Sans Mono"; font.pixelSize: 9; font.bold: true }
            Rectangle { width: 1; height: 14; color: "#495358" }
            Text { text: dashboard.orinOnline ? "VISION: ONLINE" : "VISION: STANDBY"; color: dashboard.orinOnline ? "#65D6A2" : "#879498"; font.family: "DejaVu Sans Mono"; font.pixelSize: 9; font.bold: true }
            Rectangle { width: 1; height: 14; color: "#495358" }
            Rectangle {
                width: 72
                height: 24
                color: "#20282C"
                border.color: "#647277"
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: "연결 설정"
                    color: "#DDE8E9"
                    font.family: "DejaVu Sans Mono"
                    font.pixelSize: 9
                    font.bold: true
                }
                TapHandler { onTapped: connectionPopup.open() }
            }
        }
    }

    Item {
        id: mainField
        anchors.top: systemBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: 292

        Rectangle {
            id: cameraFrame
            anchors.top: parent.top
            anchors.topMargin: 10
            anchors.left: parent.left
            anchors.leftMargin: 119
            anchors.right: parent.right
            anchors.rightMargin: 119
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 8
            color: "#07090B"
            border.color: "#59656A"
            border.width: 1
            clip: true

            Repeater {
                model: 10
                Rectangle {
                    x: index * cameraFrame.width / 10
                    width: 1
                    height: parent.height
                    color: "#111A1D"
                }
            }
            Repeater {
                model: 6
                Rectangle {
                    y: index * cameraFrame.height / 6
                    width: parent.width
                    height: 1
                    color: "#111A1D"
                }
            }

            MediaPlayer {
                id: player
                source: dashboard.rtspUrl === "" ? "" : dashboard.rtspUrl
                videoOutput: videoOutput
                autoPlay: dashboard.rtspUrl !== ""
            }

            VideoOutput {
                id: videoOutput
                anchors.fill: parent
                fillMode: VideoOutput.PreserveAspectFit
            }

            Item {
                visible: dashboard.rtspUrl === ""
                anchors.fill: parent
                Rectangle { anchors.centerIn: parent; width: 68; height: 68; color: "transparent"; border.color: "#395459"; border.width: 1 }
                Rectangle { anchors.centerIn: parent; width: 30; height: 30; color: "#18383A"; border.color: "#69D5BE"; border.width: 1 }
                Text { anchors.centerIn: parent; text: "CAM"; color: "#B4EDE4"; font.family: "DejaVu Sans Mono"; font.pixelSize: 9; font.bold: true }
                Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.verticalCenter; anchors.topMargin: 51; text: "AWAITING RTSP INPUT"; color: "#AAB8BA"; font.family: "DejaVu Sans Mono"; font.pixelSize: 10; font.bold: true; font.letterSpacing: 1.2 }
                Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.verticalCenter; anchors.topMargin: 70; text: "CAM_01 / 1280x720 / NO SIGNAL"; color: "#68787B"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8 }
            }

            Rectangle { anchors.left: parent.left; anchors.top: parent.top; width: 24; height: 2; color: "#86A2A5" }
            Rectangle { anchors.left: parent.left; anchors.top: parent.top; width: 2; height: 24; color: "#86A2A5" }
            Rectangle { anchors.right: parent.right; anchors.top: parent.top; width: 24; height: 2; color: "#86A2A5" }
            Rectangle { anchors.right: parent.right; anchors.top: parent.top; width: 2; height: 24; color: "#86A2A5" }
            Rectangle { anchors.left: parent.left; anchors.bottom: parent.bottom; width: 24; height: 2; color: "#86A2A5" }
            Rectangle { anchors.left: parent.left; anchors.bottom: parent.bottom; width: 2; height: 24; color: "#86A2A5" }
            Rectangle { anchors.right: parent.right; anchors.bottom: parent.bottom; width: 24; height: 2; color: "#86A2A5" }
            Rectangle { anchors.right: parent.right; anchors.bottom: parent.bottom; width: 2; height: 24; color: "#86A2A5" }

            Text { anchors.left: parent.left; anchors.leftMargin: 11; anchors.top: parent.top; anchors.topMargin: 10; text: "CAM_01  //  LIVE INSPECTION"; color: "#E3EBEB"; font.family: "DejaVu Sans Mono"; font.pixelSize: 9; font.bold: true }
            Text { anchors.right: parent.right; anchors.rightMargin: 11; anchors.top: parent.top; anchors.topMargin: 10; text: "FPS --   LAT --ms"; color: "#9CA9AC"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8 }
            Text { anchors.left: parent.left; anchors.leftMargin: 11; anchors.bottom: parent.bottom; anchors.bottomMargin: 9; text: dashboard.detections.length > 0 ? "VISION ALERT / TARGET LOCK" : "VISION PIPELINE / SCANNING"; color: dashboard.detections.length > 0 ? "#F0B856" : "#65D6A2"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true }

            Repeater {
                model: dashboard.detections
                delegate: Item {
                    id: detectionBox
                    required property var modelData
                    x: videoOutput.contentRect.x + modelData.x * videoOutput.contentRect.width
                    y: videoOutput.contentRect.y + modelData.y * videoOutput.contentRect.height
                    width: modelData.width * videoOutput.contentRect.width
                    height: modelData.height * videoOutput.contentRect.height
                    property int bracket: 18

                    Rectangle { x: 0; y: 0; width: detectionBox.bracket; height: 2; color: "#F0B856" }
                    Rectangle { x: 0; y: 0; width: 2; height: detectionBox.bracket; color: "#F0B856" }
                    Rectangle { x: parent.width - detectionBox.bracket; y: 0; width: detectionBox.bracket; height: 2; color: "#F0B856" }
                    Rectangle { x: parent.width - 2; y: 0; width: 2; height: detectionBox.bracket; color: "#F0B856" }
                    Rectangle { x: 0; y: parent.height - 2; width: detectionBox.bracket; height: 2; color: "#F0B856" }
                    Rectangle { x: 0; y: parent.height - detectionBox.bracket; width: 2; height: detectionBox.bracket; color: "#F0B856" }
                    Rectangle { x: parent.width - detectionBox.bracket; y: parent.height - 2; width: detectionBox.bracket; height: 2; color: "#F0B856" }
                    Rectangle { x: parent.width - 2; y: parent.height - detectionBox.bracket; width: 2; height: detectionBox.bracket; color: "#F0B856" }
                    Text { anchors.left: parent.left; anchors.bottom: parent.top; anchors.bottomMargin: 5; text: modelData.label.toUpperCase() + "  " + Math.round(modelData.confidence * 100) + "%"; color: "#FFD689"; font.family: "DejaVu Sans Mono"; font.pixelSize: 9; font.bold: true }
                }
            }
        }

        CommandGauge {
            id: driveGauge
            title: "DRIVE"
            verticalInput: true
            anchors.left: parent.left
            anchors.leftMargin: 5
            anchors.verticalCenter: cameraFrame.verticalCenter
            onChanged: function(value) { throttle = value; window.sendMotion() }
        }

        Column {
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.top: parent.top
            anchors.topMargin: 14
            width: 100
            spacing: 8
            Rectangle {
                width: 100
                height: 51
                color: emergencyLatched ? "#A7353E" : "#521C22"
                border.color: emergencyLatched ? "#FF9DA5" : "#D45C65"
                border.width: 1
                Text { anchors.centerIn: parent; text: emergencyLatched ? "STOP LATCHED" : "E-STOP"; color: "#FFF4F4"; font.family: "DejaVu Sans Mono"; font.pixelSize: 12; font.bold: true }
                TapHandler {
                    onTapped: {
                        throttle = 0
                        turn = 0
                        emergencyLatched = !emergencyLatched
                        if (emergencyLatched) dashboard.emergencyStop()
                        else dashboard.releaseEmergencyStop()
                    }
                }
            }
            Text { text: "POWER"; color: "#87969B"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true; anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: dashboard.battery; color: "#E6EEEE"; font.family: "DejaVu Sans Mono"; font.pixelSize: 18; font.bold: true; anchors.horizontalCenter: parent.horizontalCenter }
            Rectangle { width: 100; height: 4; color: "#2C373B"; Rectangle { width: parent.width * 0.72; height: parent.height; color: "#65D6A2" } }
            Rectangle { width: 100; height: 1; color: "#3B474B" }
            Text { text: "ATTITUDE"; color: "#87969B"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true; anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: "R " + dashboard.roll; color: "#C5D0D2"; font.family: "DejaVu Sans Mono"; font.pixelSize: 9; anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: "P " + dashboard.pitch; color: "#C5D0D2"; font.family: "DejaVu Sans Mono"; font.pixelSize: 9; anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: "Y " + dashboard.yaw; color: "#C5D0D2"; font.family: "DejaVu Sans Mono"; font.pixelSize: 9; anchors.horizontalCenter: parent.horizontalCenter }
        }
    }

    Rectangle {
        id: telemetryBus
        anchors.top: mainField.bottom
        anchors.topMargin: 2
        anchors.left: parent.left
        anchors.leftMargin: 8
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 8
        color: "#161B1E"
        border.color: "#3E484D"
        border.width: 1

        Rectangle { anchors.left: parent.left; anchors.top: parent.top; width: parent.width; height: 2; color: "#65D6A2" }
        Text { anchors.left: parent.left; anchors.leftMargin: 11; anchors.top: parent.top; anchors.topMargin: 10; text: "SYSTEM TELEMETRY BUS"; color: "#D7E0E1"; font.family: "DejaVu Sans Mono"; font.pixelSize: 9; font.bold: true; font.letterSpacing: 1.1 }
        Text { anchors.right: parent.right; anchors.rightMargin: 11; anchors.top: parent.top; anchors.topMargin: 10; text: emergencyLatched ? "MOTION INHIBIT ACTIVE" : "COMMAND BUS ACTIVE"; color: emergencyLatched ? "#F18B92" : "#65D6A2"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true }

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 12
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 13
            spacing: 25

            Column {
                spacing: 5
                Text { text: "MOTOR COMMAND"; color: "#859499"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true }
                Text { text: "L " + (leftMotor > 0 ? "+" : "") + leftMotor + "%   R " + (rightMotor > 0 ? "+" : "") + rightMotor + "%"; color: "#E4ECEC"; font.family: "DejaVu Sans Mono"; font.pixelSize: 12; font.bold: true }
            }
            Rectangle { width: 1; height: 29; color: "#3E484D" }
            Column {
                spacing: 5
                Text { text: "SURFACE DISTANCE / mm"; color: "#859499"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true }
                Text { text: "L " + dashboard.distances[0] + "   C " + dashboard.distances[1] + "   R " + dashboard.distances[2]; color: "#E4ECEC"; font.family: "DejaVu Sans Mono"; font.pixelSize: 11; font.bold: true }
            }
            Rectangle { width: 1; height: 29; color: "#3E484D" }
            Column {
                spacing: 5
                Text { text: "VISION ENGINE"; color: "#859499"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true }
                Text { text: dashboard.detections.length > 0 ? "ALERT / " + dashboard.detections.length + " TARGET" : "NOMINAL / NO TARGET"; color: dashboard.detections.length > 0 ? "#F0B856" : "#65D6A2"; font.family: "DejaVu Sans Mono"; font.pixelSize: 11; font.bold: true }
            }
        }

        CommandGauge {
            id: turnGauge
            title: "STEER"
            verticalInput: false
            anchors.right: parent.right
            anchors.rightMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            scale: 0.72
            transformOrigin: Item.Right
            onChanged: function(value) { turn = value; window.sendMotion() }
        }
    }

    Popup {
        id: connectionPopup
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: 536
        height: 354
        padding: 0
        onOpened: {
            dashboardHostField.text = dashboard.advertisedHost
            rtspField.text = dashboard.rtspUrl
            websocketPortField.text = dashboard.websocketPort
            connectionFeedback.text = "저장된 설정을 불러왔습니다."
            connectionFeedback.color = "#9FADB1"
        }

        background: Rectangle {
            color: "#151A1D"
            border.color: "#68777C"
            border.width: 1
        }

        contentItem: Item {
            anchors.fill: parent

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 44
                color: "#1E2529"
                border.color: "#3E4A4F"
                border.width: 1
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 16
                    anchors.verticalCenter: parent.verticalCenter
                    text: "연결 설정  /  CONNECTION CONFIGURATION"
                    color: "#EEF3F3"
                    font.family: "DejaVu Sans Mono"
                    font.pixelSize: 12
                    font.bold: true
                }
                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    text: "×"
                    color: "#B8C5C7"
                    font.pixelSize: 22
                    TapHandler { onTapped: connectionPopup.close() }
                }
            }

            Column {
                anchors.top: parent.top
                anchors.topMargin: 61
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 12

                Column {
                    spacing: 5
                    Text { text: "대시보드 Tailscale 주소"; color: "#D9E3E4"; font.pixelSize: 11; font.bold: true }
                    Text { text: "Nano B01과 Orin이 접속할 WebSocket 주소입니다."; color: "#819196"; font.pixelSize: 9 }
                    TextField {
                        id: dashboardHostField
                        width: parent.width
                        height: 32
                        color: "#ECF3F3"
                        font.family: "DejaVu Sans Mono"
                        font.pixelSize: 12
                        placeholderText: "예: 100.74.141.112"
                        placeholderTextColor: "#66777B"
                        selectByMouse: true
                        background: Rectangle { color: "#0C1012"; border.color: "#4C5A5F"; border.width: 1 }
                    }
                }

                Column {
                    spacing: 5
                    Text { text: "카메라 RTSP 주소"; color: "#D9E3E4"; font.pixelSize: 11; font.bold: true }
                    Text { text: "저장 후 재실행해도 자동으로 영상 수신을 시도합니다."; color: "#819196"; font.pixelSize: 9 }
                    TextField {
                        id: rtspField
                        width: parent.width
                        height: 32
                        color: "#ECF3F3"
                        font.family: "DejaVu Sans Mono"
                        font.pixelSize: 12
                        placeholderText: "rtsp://<nano-ip>:8554/robot"
                        placeholderTextColor: "#66777B"
                        selectByMouse: true
                        background: Rectangle { color: "#0C1012"; border.color: "#4C5A5F"; border.width: 1 }
                    }
                }

                Row {
                    spacing: 14
                    Column {
                        spacing: 5
                        Text { text: "WebSocket 포트"; color: "#D9E3E4"; font.pixelSize: 11; font.bold: true }
                        TextField {
                            id: websocketPortField
                            width: 130
                            height: 32
                            color: "#ECF3F3"
                            font.family: "DejaVu Sans Mono"
                            font.pixelSize: 12
                            inputMethodHints: Qt.ImhDigitsOnly
                            selectByMouse: true
                            background: Rectangle { color: "#0C1012"; border.color: "#4C5A5F"; border.width: 1 }
                        }
                    }
                    Column {
                        spacing: 5
                        Text { text: "Nano/Orin 연결 대상"; color: "#819196"; font.pixelSize: 10; font.bold: true }
                        Text { text: dashboard.dashboardEndpoint; color: "#65D6A2"; font.family: "DejaVu Sans Mono"; font.pixelSize: 11; font.bold: true }
                    }
                }

                Text {
                    id: connectionFeedback
                    color: "#9FADB1"
                    font.pixelSize: 10
                }
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 16
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 14
                spacing: 8
                Button {
                    text: "취소"
                    onClicked: connectionPopup.close()
                    contentItem: Text { text: parent.text; color: "#C6D0D2"; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle { color: "#252D31"; border.color: "#59666B"; border.width: 1 }
                }
                Button {
                    text: "저장 및 적용"
                    onClicked: {
                        const port = Number(websocketPortField.text)
                        if (dashboard.saveConnectionSettings(dashboardHostField.text, rtspField.text, port)) {
                            connectionFeedback.text = "저장됨 — 영상과 연결 설정을 자동 적용합니다."
                            connectionFeedback.color = "#65D6A2"
                        } else {
                            connectionFeedback.text = "저장 실패 — 주소와 포트를 다시 확인하세요."
                            connectionFeedback.color = "#F18B92"
                        }
                    }
                    contentItem: Text { text: parent.text; color: "#071110"; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle { color: "#65D6A2"; border.color: "#A9F1E1"; border.width: 1 }
                }
            }
        }
    }
}
