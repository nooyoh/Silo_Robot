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
    title: "SiloRobot Inspection Console"
    color: "#161A1D"

    property int throttle: 0
    property int turn: 0
    property bool emergencyLatched: false

    function sendMotion() {
        if (!emergencyLatched)
            dashboard.sendMove(throttle, turn)
    }

    Timer {
        interval: 50
        running: !window.emergencyLatched && (driveAxis.held || steerAxis.held)
        repeat: true
        onTriggered: window.sendMotion()
    }

    Rectangle {
        anchors.fill: parent
        color: "#161A1D"
    }

    Rectangle {
        id: header
        height: 48
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        color: "#1D2328"
        border.color: "#343E45"
        border.width: 1

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 15
            anchors.verticalCenter: parent.verticalCenter
            spacing: 9

            Rectangle {
                width: 10
                height: 10
                radius: 5
                anchors.verticalCenter: parent.verticalCenter
                color: dashboard.robotOnline ? "#5BBEAF" : "#7B878F"
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "SILOROBOT"
                color: "#F1F4F5"
                font.pixelSize: 18
                font.bold: true
                font.letterSpacing: 1.8
            }
            Rectangle {
                width: 1
                height: 19
                anchors.verticalCenter: parent.verticalCenter
                color: "#4A555D"
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "INSPECTION CONSOLE"
                color: "#9AA8B1"
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 1
            }
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 15
            anchors.verticalCenter: parent.verticalCenter
            spacing: 14

            Row {
                spacing: 5
                Rectangle {
                    width: 7; height: 7; radius: 4
                    anchors.verticalCenter: parent.verticalCenter
                    color: dashboard.robotOnline ? "#5BBEAF" : "#7B878F"
                }
                Text {
                    text: "ROBOT"
                    color: "#C4CDD2"
                    font.pixelSize: 10
                    font.bold: true
                }
            }
            Row {
                spacing: 5
                Rectangle {
                    width: 7; height: 7; radius: 4
                    anchors.verticalCenter: parent.verticalCenter
                    color: dashboard.orinOnline ? "#E4AA52" : "#7B878F"
                }
                Text {
                    text: "VISION"
                    color: "#C4CDD2"
                    font.pixelSize: 10
                    font.bold: true
                }
            }
            Text {
                text: emergencyLatched ? "MOTION INHIBITED" : "CONTROL READY"
                color: emergencyLatched ? "#F18A91" : "#9AA8B1"
                font.pixelSize: 10
                font.bold: true
            }
        }
    }

    Item {
        id: workspace
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 9

        VirtualAxisProduction {
            id: driveAxis
            title: "DRIVE"
            vertical: true
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            onChanged: function(value) {
                throttle = value
                window.sendMotion()
            }
        }

        Item {
            id: centerColumn
            anchors.left: driveAxis.right
            anchors.leftMargin: 9
            anchors.right: sidePanel.left
            anchors.rightMargin: 9
            anchors.top: parent.top
            anchors.bottom: parent.bottom

            Rectangle {
                id: cameraPanel
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: Math.min(width * 0.61, 279)
                color: "#0D1114"
                border.color: "#3A454C"
                border.width: 1
                radius: 6
                clip: true

                Rectangle {
                    id: cameraHeader
                    height: 29
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    color: "#20272C"

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 11
                        anchors.verticalCenter: parent.verticalCenter
                        text: "LIVE INSPECTION"
                        color: "#D9E0E3"
                        font.pixelSize: 10
                        font.bold: true
                        font.letterSpacing: 1
                    }
                    Row {
                        anchors.right: parent.right
                        anchors.rightMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 9
                        Text { text: "CAM 01"; color: "#A7B5BC"; font.pixelSize: 9; font.bold: true }
                        Text { text: "720P / 30"; color: "#7D8B93"; font.pixelSize: 9; font.bold: true }
                    }
                }

                Item {
                    id: videoViewport
                    anchors.top: cameraHeader.bottom
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right

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
                        anchors.fill: parent
                        visible: dashboard.rtspUrl === ""
                        Rectangle {
                            anchors.centerIn: parent
                            width: 102
                            height: 62
                            color: "transparent"
                            border.color: "#53616A"
                            border.width: 2
                            radius: 3
                            Rectangle {
                                width: 13; height: 13; radius: 7
                                anchors.centerIn: parent
                                color: "#53616A"
                            }
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: parent.verticalCenter
                            anchors.topMargin: 49
                            text: "AWAITING VIDEO SOURCE"
                            color: "#A2AFB6"
                            font.pixelSize: 12
                            font.bold: true
                            font.letterSpacing: 1.1
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: parent.verticalCenter
                            anchors.topMargin: 70
                            text: "RTSP link will appear here"
                            color: "#687780"
                            font.pixelSize: 10
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
                                border.color: "#E4AA52"
                                border.width: 2
                            }
                            Rectangle {
                                width: defectLabel.implicitWidth + 12
                                height: 20
                                anchors.left: parent.left
                                anchors.bottom: parent.top
                                color: "#E4AA52"
                                Text {
                                    id: defectLabel
                                    anchors.centerIn: parent
                                    text: modelData.label.toUpperCase() + "  " + Math.round(modelData.confidence * 100) + "%"
                                    color: "#242015"
                                    font.pixelSize: 10
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
                        text: dashboard.detections.length > 0 ? "DEFECT DETECTED" : "SCAN ACTIVE"
                        color: dashboard.detections.length > 0 ? "#E4AA52" : "#AAB6BC"
                        font.pixelSize: 10
                        font.bold: true
                        font.letterSpacing: 0.8
                    }
                }
            }

            Rectangle {
                id: inspectionSummary
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 119
                color: "#20272C"
                border.color: "#3A454C"
                border.width: 1
                radius: 6

                Row {
                    anchors.fill: parent
                    anchors.margins: 13
                    spacing: 16

                    Column {
                        width: 142
                        spacing: 7
                        Text { text: "INSPECTION STATUS"; color: "#91A0A9"; font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.8 }
                        Text {
                            text: dashboard.detections.length > 0 ? "ATTENTION REQUIRED" : "NO ACTIVE DEFECT"
                            color: dashboard.detections.length > 0 ? "#E4AA52" : "#5BBEAF"
                            font.pixelSize: 13
                            font.bold: true
                        }
                        Text {
                            text: dashboard.orinOnline ? "Vision server reporting" : "Vision server waiting"
                            color: "#A6B2B8"
                            font.pixelSize: 10
                        }
                    }

                    Rectangle { width: 1; height: parent.height - 6; color: "#3A454C" }

                    Column {
                        width: 142
                        spacing: 7
                        Text { text: "SURFACE PROFILE"; color: "#91A0A9"; font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.8 }
                        Text { text: "L  " + dashboard.distances[0] + "    C  " + dashboard.distances[1]; color: "#E1E7E9"; font.pixelSize: 12; font.bold: true }
                        Text { text: "R  " + dashboard.distances[2]; color: "#A6B2B8"; font.pixelSize: 11 }
                    }
                }
            }
        }

        Item {
            id: sidePanel
            width: 176
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom

            Rectangle {
                id: estop
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 73
                color: emergencyLatched ? "#8E303A" : "#C13E49"
                border.color: emergencyLatched ? "#F5A7AC" : "#EE8089"
                border.width: 2
                radius: 6

                Text {
                    anchors.centerIn: parent
                    text: emergencyLatched ? "MOTION STOPPED\nTAP TO RELEASE" : "EMERGENCY STOP"
                    horizontalAlignment: Text.AlignHCenter
                    color: "#FFFFFF"
                    font.pixelSize: emergencyLatched ? 12 : 16
                    font.bold: true
                    font.letterSpacing: emergencyLatched ? 0.5 : 1
                }
                TapHandler {
                    onTapped: {
                        throttle = 0
                        turn = 0
                        emergencyLatched = !emergencyLatched
                        if (emergencyLatched)
                            dashboard.emergencyStop()
                        else
                            dashboard.releaseEmergencyStop()
                    }
                }
            }

            Rectangle {
                id: telemetry
                anchors.top: estop.bottom
                anchors.topMargin: 9
                anchors.left: parent.left
                anchors.right: parent.right
                height: 174
                color: "#20272C"
                border.color: "#3A454C"
                border.width: 1
                radius: 6

                Column {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    Text { text: "ROBOT HEALTH"; color: "#91A0A9"; font.pixelSize: 10; font.bold: true; font.letterSpacing: 1 }
                    Row {
                        spacing: 8
                        Text { text: "BATTERY"; color: "#A7B4BA"; font.pixelSize: 10; font.bold: true }
                        Text { text: dashboard.battery; color: "#F0F3F4"; font.pixelSize: 14; font.bold: true }
                    }
                    Rectangle { width: parent.width; height: 4; radius: 2; color: "#3E4A52" }
                    Rectangle { width: parent.width * 0.72; height: 4; radius: 2; color: "#5BBEAF"; anchors.topMargin: -12 }
                    Rectangle { width: parent.width; height: 1; color: "#3A454C" }
                    Text { text: "ATTITUDE"; color: "#91A0A9"; font.pixelSize: 10; font.bold: true }
                    Text { text: "ROLL " + dashboard.roll + "   PITCH " + dashboard.pitch; color: "#D3DCE0"; font.pixelSize: 10 }
                    Text { text: "YAW  " + dashboard.yaw; color: "#D3DCE0"; font.pixelSize: 10 }
                }
            }

            VirtualAxisProduction {
                id: steerAxis
                title: "STEER"
                vertical: false
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                onChanged: function(value) {
                    turn = value
                    window.sendMotion()
                }
            }
        }
    }
}
