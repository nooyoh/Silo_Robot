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
    title: "SiloRobot Dashboard"
    color: "#0B121B"

    property int throttle: 0
    property int turn: 0
    property bool stopped: false

    function sendMotion() {
        if (!stopped)
            dashboard.sendMove(throttle, turn)
    }

    Rectangle {
        anchors.fill: parent
        color: "#0B121B"
    }

    Rectangle {
        id: topBar
        height: 42
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        color: "#101D29"
        border.color: "#243B4F"
        border.width: 1

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            text: "SILOROBOT"
            color: "#E9F7FF"
            font.pixelSize: 19
            font.bold: true
            font.letterSpacing: 2
        }

        Rectangle {
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            width: statusText.implicitWidth + 20
            height: 24
            radius: 12
            color: dashboard.robotOnline ? "#173F35" : "#3A2530"
            border.color: dashboard.robotOnline ? "#38D68C" : "#E76A7D"

            Text {
                id: statusText
                anchors.centerIn: parent
                text: dashboard.connectionSummary
                color: dashboard.robotOnline ? "#80F5B6" : "#FF9EAD"
                font.pixelSize: 11
                font.bold: true
            }
        }
    }

    Item {
        id: content
        anchors.top: topBar.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right

        Rectangle {
            id: videoFrame
            anchors.left: parent.left
            anchors.leftMargin: 124
            anchors.right: parent.right
            anchors.rightMargin: 148
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.margins: 10
            radius: 10
            color: "#020609"
            border.color: "#2F506A"
            border.width: 2
            clip: true

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

            Column {
                anchors.centerIn: parent
                visible: dashboard.rtspUrl === ""
                spacing: 8
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "VIDEO FEED WAITING"
                    color: "#8FAEC1"
                    font.pixelSize: 19
                    font.bold: true
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Start with  --rtsp rtsp://<nano-tailscale-ip>:8554/robot"
                    color: "#5C778B"
                    font.pixelSize: 11
                }
            }

            Repeater {
                model: dashboard.detections
                delegate: Item {
                    required property var modelData
                    x: videoOutput.contentRect.x + modelData.x * videoOutput.contentRect.width
                    y: videoOutput.contentRect.y + modelData.y * videoOutput.contentRect.height
                    width: modelData.width * videoOutput.contentRect.width
                    height: modelData.height * videoOutput.contentRect.height

                    Rectangle {
                        anchors.fill: parent
                        color: "transparent"
                        border.color: "#FFB52B"
                        border.width: 3
                    }
                    Rectangle {
                        width: labelText.implicitWidth + 12
                        height: 22
                        anchors.left: parent.left
                        anchors.bottom: parent.top
                        color: "#FFB52B"
                        Text {
                            id: labelText
                            anchors.centerIn: parent
                            text: modelData.label.toUpperCase() + " " + Math.round(modelData.confidence * 100) + "%"
                            color: "#1C1606"
                            font.pixelSize: 11
                            font.bold: true
                        }
                    }
                }
            }

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 10
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                text: "RTSP 720P / 30 FPS"
                color: "#89A8BC"
                font.pixelSize: 10
                font.bold: true
            }
        }

        VirtualAxis {
            id: throttleAxis
            axis: "throttle"
            title: "DRIVE"
            vertical: true
            anchors.left: parent.left
            anchors.leftMargin: 8
            anchors.verticalCenter: videoFrame.verticalCenter
            onChanged: function(value) {
                throttle = value
                window.sendMotion()
            }
        }

        VirtualAxis {
            id: turnAxis
            axis: "turn"
            title: "STEER"
            vertical: false
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10
            onChanged: function(value) {
                turn = value
                window.sendMotion()
            }
        }

        Rectangle {
            id: stopButton
            width: 130
            height: 90
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.top: parent.top
            anchors.topMargin: 10
            radius: 16
            color: stopped ? "#621A25" : "#C83345"
            border.color: stopped ? "#FF8795" : "#FFB1BB"
            border.width: 2

            Text {
                anchors.centerIn: parent
                text: stopped ? "STOPPED\nTAP TO RELEASE" : "EMERGENCY\nSTOP"
                horizontalAlignment: Text.AlignHCenter
                color: "white"
                font.pixelSize: 16
                font.bold: true
            }
            TapHandler {
                onTapped: {
                    stopped = !stopped
                    throttle = 0
                    turn = 0
                    if (stopped)
                        dashboard.emergencyStop()
                    else
                        dashboard.releaseEmergencyStop()
                }
            }
        }

        Rectangle {
            id: telemetryPanel
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.top: stopButton.bottom
            anchors.topMargin: 8
            anchors.bottom: turnAxis.top
            anchors.bottomMargin: 8
            width: 130
            radius: 12
            color: "#101D29"
            border.color: "#2A475E"
            border.width: 1

            Column {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 6
                Text { text: "TELEMETRY"; color: "#86A9BD"; font.pixelSize: 11; font.bold: true }
                Text { text: "BAT  " + dashboard.battery; color: "#E8F5FC"; font.pixelSize: 13; font.bold: true }
                Rectangle { width: parent.width; height: 1; color: "#314C60" }
                Text { text: "R  " + dashboard.roll; color: "#C2D9E6"; font.pixelSize: 11 }
                Text { text: "P  " + dashboard.pitch; color: "#C2D9E6"; font.pixelSize: 11 }
                Text { text: "Y  " + dashboard.yaw; color: "#C2D9E6"; font.pixelSize: 11 }
                Rectangle { width: parent.width; height: 1; color: "#314C60" }
                Text { text: "DISTANCE"; color: "#86A9BD"; font.pixelSize: 10; font.bold: true }
                Text { text: "L  " + dashboard.distances[0]; color: "#DDECF4"; font.pixelSize: 10 }
                Text { text: "C  " + dashboard.distances[1]; color: "#DDECF4"; font.pixelSize: 10 }
                Text { text: "R  " + dashboard.distances[2]; color: "#DDECF4"; font.pixelSize: 10 }
            }
        }
    }
}
