import QtQuick

Item {
    id: root
    required property string axis
    required property string title
    property bool vertical: true
    property int value: 0
    property string positiveLabel: vertical ? "FWD" : "RIGHT"
    property string negativeLabel: vertical ? "REV" : "LEFT"
    signal changed(int value)

    implicitWidth: vertical ? 112 : 220
    implicitHeight: vertical ? 220 : 112

    function updateFromPoint(pointX, pointY) {
        var ratio = vertical
                ? 1.0 - (pointY / height) * 2.0
                : (pointX / width) * 2.0 - 1.0
        value = Math.max(-100, Math.min(100, Math.round(ratio * 100)))
        changed(value)
    }

    function reset() {
        value = 0
        changed(0)
    }

    Rectangle {
        anchors.fill: parent
        radius: 16
        color: "#172433"
        border.color: root.value !== 0 ? "#31C5F4" : "#39536B"
        border.width: 2
    }

    Text {
        anchors.top: parent.top
        anchors.topMargin: 10
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.title
        color: "#A9C5D8"
        font.pixelSize: 13
        font.bold: true
        font.letterSpacing: 1.5
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: root.vertical ? 35 : 42
        visible: root.vertical
        text: root.positiveLabel
        color: "#7A99AF"
        font.pixelSize: 11
        font.bold: true
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: root.vertical ? 14 : 42
        visible: root.vertical
        text: root.negativeLabel
        color: "#7A99AF"
        font.pixelSize: 11
        font.bold: true
    }

    Text {
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.leftMargin: 13
        visible: !root.vertical
        text: root.negativeLabel
        color: "#7A99AF"
        font.pixelSize: 11
        font.bold: true
    }

    Text {
        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right
        anchors.rightMargin: 13
        visible: !root.vertical
        text: root.positiveLabel
        color: "#7A99AF"
        font.pixelSize: 11
        font.bold: true
    }

    Rectangle {
        id: centerLine
        width: root.vertical ? parent.width - 28 : 2
        height: root.vertical ? 2 : parent.height - 28
        anchors.centerIn: parent
        color: "#4B657B"
    }

    Rectangle {
        width: root.vertical ? parent.width - 42 : 8
        height: root.vertical ? 8 : parent.height - 42
        anchors.centerIn: parent
        color: "#31C5F4"
        opacity: 0.35
        visible: root.value !== 0
    }

    Rectangle {
        width: root.vertical ? parent.width - 28 : 30
        height: root.vertical ? 30 : parent.height - 28
        radius: 13
        x: root.vertical ? 14 : (parent.width - width) / 2 + (root.value / 100) * ((parent.width - width) / 2 - 15)
        y: root.vertical ? (parent.height - height) / 2 - (root.value / 100) * ((parent.height - height) / 2 - 15) : 14
        color: root.value === 0 ? "#4A657B" : "#31C5F4"
        border.color: "#D8F4FF"
        border.width: 1
    }

    Text {
        anchors.centerIn: parent
        text: root.value + "%"
        color: "#F2FAFF"
        font.pixelSize: 17
        font.bold: true
        z: 2
    }

    MultiPointTouchArea {
        anchors.fill: parent
        minimumTouchPoints: 1
        maximumTouchPoints: 1
        touchPoints: [TouchPoint { id: touchPoint }]
        onPressed: root.updateFromPoint(touchPoint.x, touchPoint.y)
        onUpdated: root.updateFromPoint(touchPoint.x, touchPoint.y)
        onReleased: root.reset()
        onCanceled: root.reset()
    }
}
