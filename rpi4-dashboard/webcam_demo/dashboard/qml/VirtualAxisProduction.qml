import QtQuick

Item {
    id: root

    required property string title
    property bool vertical: true
    property int value: 0
    property bool held: false
    property string positiveLabel: vertical ? "FORWARD" : "RIGHT"
    property string negativeLabel: vertical ? "REVERSE" : "LEFT"
    signal changed(int value)

    implicitWidth: vertical ? 116 : 176
    implicitHeight: vertical ? 410 : 116

    function updateFromPoint(pointX, pointY) {
        const ratio = vertical
                ? 1.0 - (pointY / height) * 2.0
                : (pointX / width) * 2.0 - 1.0
        value = Math.max(-100, Math.min(100, Math.round(ratio * 100)))
        changed(value)
    }

    function reset() {
        held = false
        if (value !== 0) {
            value = 0
            changed(0)
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "#22292E"
        border.color: root.held ? "#5BBEAF" : "#414B52"
        border.width: root.held ? 2 : 1
        radius: 6
    }

    Text {
        anchors.top: parent.top
        anchors.topMargin: 13
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.title
        color: "#B7C2C9"
        font.pixelSize: 11
        font.bold: true
        font.letterSpacing: 1.2
    }

    Text {
        visible: root.vertical
        anchors.top: parent.top
        anchors.topMargin: 40
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.positiveLabel
        color: "#71808A"
        font.pixelSize: 9
        font.bold: true
    }

    Text {
        visible: root.vertical
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 16
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.negativeLabel
        color: "#71808A"
        font.pixelSize: 9
        font.bold: true
    }

    Text {
        visible: !root.vertical
        anchors.left: parent.left
        anchors.leftMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        text: root.negativeLabel
        color: "#71808A"
        font.pixelSize: 9
        font.bold: true
    }

    Text {
        visible: !root.vertical
        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        text: root.positiveLabel
        color: "#71808A"
        font.pixelSize: 9
        font.bold: true
    }

    Rectangle {
        id: track
        width: root.vertical ? 4 : parent.width - 58
        height: root.vertical ? parent.height - 128 : 4
        anchors.centerIn: parent
        color: "#47535B"
        radius: 2
    }

    Rectangle {
        width: root.vertical ? 4 : Math.abs(root.value / 100) * (track.width / 2)
        height: root.vertical ? Math.abs(root.value / 100) * (track.height / 2) : 4
        x: root.vertical ? track.x : (root.value >= 0 ? track.x + track.width / 2 : track.x + track.width / 2 - width)
        y: root.vertical ? (root.value >= 0 ? track.y + track.height / 2 - height : track.y + track.height / 2) : track.y
        color: "#5BBEAF"
        radius: 2
    }

    Rectangle {
        width: root.vertical ? 70 : 32
        height: root.vertical ? 32 : 70
        radius: 5
        x: root.vertical ? (parent.width - width) / 2
                         : track.x + track.width / 2 + (root.value / 100) * (track.width / 2) - width / 2
        y: root.vertical ? track.y + track.height / 2 - (root.value / 100) * (track.height / 2) - height / 2
                         : (parent.height - height) / 2
        color: root.held ? "#5BBEAF" : "#64737D"
        border.color: "#D7E4E8"
        border.width: 1

        Text {
            anchors.centerIn: parent
            text: root.value + "%"
            color: root.held ? "#102523" : "#F0F4F5"
            font.pixelSize: 12
            font.bold: true
        }
    }

    MultiPointTouchArea {
        anchors.fill: parent
        minimumTouchPoints: 1
        maximumTouchPoints: 1
        touchPoints: [TouchPoint { id: touchPoint }]
        onPressed: {
            root.held = true
            root.updateFromPoint(touchPoint.x, touchPoint.y)
        }
        onUpdated: root.updateFromPoint(touchPoint.x, touchPoint.y)
        onReleased: root.reset()
        onCanceled: root.reset()
    }
}
