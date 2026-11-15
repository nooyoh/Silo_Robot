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
    title: "SiloRobot"
    color: "#070A0C"

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
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#071013" }
            GradientStop { position: 0.5; color: "#10191C" }
            GradientStop { position: 1.0; color: "#070A0C" }
        }
    }

    Item {
        id: viewer
        anchors.top: parent.top
        anchors.topMargin: 44
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 48
        anchors.left: parent.left
        anchors.leftMargin: 16
        anchors.right: parent.right
        anchors.rightMargin: 16
        clip: true

        Rectangle {
            anchors.fill: parent
            radius: 18
            color: "#0D1518"
            border.color: "#234046"
            border.width: 1
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
            fillMode: VideoOutput.PreserveAspectCrop
        }

        Item {
            visible: dashboard.rtspUrl === ""
            anchors.fill: parent

            Rectangle {
                width: parent.width * 0.9
                height: 1
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.verticalCenter: parent.verticalCenter
                color: "#1D3237"
            }
            Rectangle {
                width: 1
                height: parent.height * 0.78
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.verticalCenter: parent.verticalCenter
                color: "#1D3237"
            }
            Rectangle {
                width: 92
                height: 92
                radius: 46
                anchors.centerIn: parent
                color: "transparent"
                border.color: "#477279"
                border.width: 1
            }
            Rectangle {
                width: 54
                height: 54
                radius: 27
                anchors.centerIn: parent
                color: "#183238"
                border.color: "#70CDBF"
                border.width: 1
            }
            Text {
                anchors.centerIn: parent
                text: "CAM"
                color: "#B3E5DE"
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 1
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.verticalCenter
                anchors.topMargin: 66
                text: "LIVE INSPECTION FEED"
                color: "#C1D2D5"
                font.pixelSize: 12
                font.bold: true
                font.letterSpacing: 2
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.verticalCenter
                anchors.topMargin: 88
                text: "Awaiting camera stream"
                color: "#6E858B"
                font.pixelSize: 10
            }
        }

        Repeater {
            model: dashboard.detections
            delegate: Item {
                id: detectionBox
                required property var modelData
                x: videoOutput.contentRect.x + modelData.x * videoOutput.contentRect.width
                y: videoOutput.contentRect.y + modelData.y * videoOutput.contentRect.height
                width: modelData.width * videoOutput.contentRect.width
                height: modelData.height * videoOutput.contentRect.height

                property int cornerSize: 18
                Repeater {
                    model: [
                        { x: 0, y: 0, rotation: 0 },
                        { x: parent.width, y: 0, rotation: 90 },
                        { x: parent.width, y: parent.height, rotation: 180 },
                        { x: 0, y: parent.height, rotation: 270 }
                    ]
                    delegate: Item {
                        required property var modelData
                        x: modelData.x
                        y: modelData.y
                        rotation: modelData.rotation
                        transformOrigin: Item.Center
                        Rectangle { width: detectionBox.cornerSize; height: 2; color: "#F2B654" }
                        Rectangle { width: 2; height: detectionBox.cornerSize; color: "#F2B654" }
                    }
                }
                Rectangle {
                    anchors.left: parent.left
                    anchors.bottom: parent.top
                    anchors.bottomMargin: 5
                    width: defectText.implicitWidth + 14
                    height: 24
                    radius: 12
                    color: "#241C0E"
                    border.color: "#F2B654"
                    border.width: 1
                    Text {
                        id: defectText
                        anchors.centerIn: parent
                        text: modelData.label.toUpperCase() + "  " + Math.round(modelData.confidence * 100) + "%"
                        color: "#FFD898"
                        font.pixelSize: 10
                        font.bold: true
                    }
                }
            }
        }
    }

    Rectangle {
        id: topFade
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 70
        gradient: Gradient {
            GradientStop { position: 0; color: "#D0000000" }
            GradientStop { position: 1; color: "#00000000" }
        }
    }

    Row {
        anchors.left: parent.left
        anchors.leftMargin: 23
        anchors.top: parent.top
        anchors.topMargin: 15
        spacing: 9
        Text {
            text: "SAILOBOT"
            color: "#F2F6F6"
            font.pixelSize: 17
            font.bold: true
            font.letterSpacing: 2.2
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "INSPECTION"
            color: "#79CABC"
            font.pixelSize: 10
            font.bold: true
            font.letterSpacing: 1.5
        }
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: 22
        anchors.top: parent.top
        anchors.topMargin: 17
        spacing: 12
        Row {
            spacing: 5
            Rectangle { width: 6; height: 6; radius: 3; anchors.verticalCenter: parent.verticalCenter; color: dashboard.robotOnline ? "#6FD3C4" : "#6D7A80" }
            Text { text: dashboard.robotOnline ? "ROBOT LINK" : "ROBOT OFFLINE"; color: "#CEDADD"; font.pixelSize: 10; font.bold: true }
        }
        Row {
            spacing: 5
            Rectangle { width: 6; height: 6; radius: 3; anchors.verticalCenter: parent.verticalCenter; color: dashboard.orinOnline ? "#F2B654" : "#6D7A80" }
            Text { text: dashboard.orinOnline ? "VISION" : "VISION WAIT"; color: "#9EACB0"; font.pixelSize: 10; font.bold: true }
        }
    }

    MotionAxis {
        id: driveAxis
        title: "DRIVE"
        vertical: true
        anchors.left: parent.left
        anchors.leftMargin: 31
        anchors.verticalCenter: parent.verticalCenter
        onChanged: function(value) {
            throttle = value
            window.sendMotion()
        }
    }

    Column {
        anchors.right: parent.right
        anchors.rightMargin: 31
        anchors.top: parent.top
        anchors.topMargin: 84
        width: 98
        spacing: 14

        Rectangle {
            width: 66
            height: 66
            radius: 33
            anchors.horizontalCenter: parent.horizontalCenter
            color: emergencyLatched ? "#A13C45" : "#3A1419"
            border.color: emergencyLatched ? "#F2A4A9" : "#D26069"
            border.width: 2
            Text {
                anchors.centerIn: parent
                text: emergencyLatched ? "HOLD\nSTOP" : "STOP"
                horizontalAlignment: Text.AlignHCenter
                color: "#FFF5F5"
                font.pixelSize: 13
                font.bold: true
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

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "BATTERY"
            color: "#91A1A6"
            font.pixelSize: 9
            font.bold: true
            font.letterSpacing: 1.4
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: dashboard.battery
            color: "#EEF5F4"
            font.pixelSize: 19
            font.bold: true
        }
        Rectangle {
            width: 92
            height: 2
            radius: 1
            anchors.horizontalCenter: parent.horizontalCenter
            color: "#43545A"
            Rectangle { width: parent.width * 0.72; height: parent.height; radius: 1; color: "#6FD3C4" }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "R " + dashboard.roll + "  P " + dashboard.pitch
            color: "#A7B7B9"
            font.pixelSize: 9
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Y " + dashboard.yaw
            color: "#A7B7B9"
            font.pixelSize: 9
        }
    }

    Rectangle {
        id: lowerHud
        anchors.left: parent.left
        anchors.leftMargin: 130
        anchors.right: parent.right
        anchors.rightMargin: 130
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 13
        height: 76
        radius: 18
        color: "#D1111B1E"
        border.color: "#3A5156"
        border.width: 1

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 18
            anchors.verticalCenter: parent.verticalCenter
            spacing: 12
            Column {
                spacing: 5
                Text { text: "SURFACE PROFILE"; color: "#819297"; font.pixelSize: 9; font.bold: true; font.letterSpacing: 1.2 }
                Text { text: "L " + dashboard.distances[0] + "   C " + dashboard.distances[1] + "   R " + dashboard.distances[2]; color: "#E3ECEC"; font.pixelSize: 11; font.bold: true }
            }
            Rectangle { width: 1; height: 33; anchors.verticalCenter: parent.verticalCenter; color: "#405257" }
            Column {
                spacing: 5
                Text { text: "ANALYSIS"; color: "#819297"; font.pixelSize: 9; font.bold: true; font.letterSpacing: 1.2 }
                Text {
                    text: dashboard.detections.length > 0 ? "DEFECT DETECTED" : "SCANNING SURFACE"
                    color: dashboard.detections.length > 0 ? "#F2B654" : "#79CABC"
                    font.pixelSize: 11
                    font.bold: true
                }
            }
        }

        MotionAxis {
            id: steerAxis
            title: "STEER"
            vertical: false
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            onChanged: function(value) {
                turn = value
                window.sendMotion()
            }
        }
    }
}
