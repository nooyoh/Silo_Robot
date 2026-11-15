import QtQuick

Item {
    id: root

    required property string title
    property bool vertical: true
    property int value: 0
    property bool held: false
    property string positiveLabel: vertical ? "FWD" : "R"
    property string negativeLabel: vertical ? "REV" : "L"
    signal changed(int value)

    implicitWidth: vertical ? 92 : 218
    implicitHeight: vertical ? 302 : 88

    function updateFromPoint(pointX, pointY) {
        const axis = vertical ? 1 - (pointY / height) * 2 : (pointX / width) * 2 - 1
        value = Math.max(-100, Math.min(100, Math.round(axis * 100)))
        changed(value)
    }

    function reset() {
        held = false
        if (value !== 0) {
            value = 0
            changed(0)
        }
    }

    Text {
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.title
        color: root.held ? "#AEEFE6" : "#9CAAAF"
        font.pixelSize: 10
        font.bold: true
        font.letterSpacing: 2
    }

    Text {
        visible: root.vertical
        anchors.top: parent.top
        anchors.topMargin: 29
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.positiveLabel
        color: "#718086"
        font.pixelSize: 9
        font.bold: true
    }

    Text {
        visible: root.vertical
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 3
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.negativeLabel
        color: "#718086"
        font.pixelSize: 9
        font.bold: true
    }

    Text {
        visible: !root.vertical
        anchors.left: parent.left
        anchors.leftMargin: 2
        anchors.verticalCenter: parent.verticalCenter
        text: root.negativeLabel
        color: "#718086"
        font.pixelSize: 9
        font.bold: true
    }

    Text {
        visible: !root.vertical
        anchors.right: parent.right
        anchors.rightMargin: 2
        anchors.verticalCenter: parent.verticalCenter
        text: root.positiveLabel
        color: "#718086"
        font.pixelSize: 9
        font.bold: true
    }

    Rectangle {
        id: track
        width: root.vertical ? 3 : parent.width - 52
        height: root.vertical ? parent.height - 82 : 3
        radius: 2
        anchors.centerIn: parent
        color: "#758289"
        opacity: 0.5
    }

    Rectangle {
        width: root.vertical ? 3 : Math.abs(root.value) / 100 * track.width / 2
        height: root.vertical ? Math.abs(root.value) / 100 * track.height / 2 : 3
        radius: 2
        x: root.vertical ? track.x : (root.value < 0 ? track.x + track.width / 2 - width : track.x + track.width / 2)
        y: root.vertical ? (root.value > 0 ? track.y + track.height / 2 - height : track.y + track.height / 2) : track.y
        color: "#69D4C4"
    }

    Rectangle {
        width: root.vertical ? 52 : 46
        height: root.vertical ? 46 : 52
        radius: width / 2
        x: root.vertical ? (parent.width - width) / 2
                         : track.x + track.width / 2 + root.value / 100 * track.width / 2 - width / 2
        y: root.vertical ? track.y + track.height / 2 - root.value / 100 * track.height / 2 - height / 2
                         : (parent.height - height) / 2
        color: root.held ? "#77D8C9" : "#314046"
        border.color: root.held ? "#D6FFF9" : "#627078"
        border.width: 1

        Text {
            anchors.centerIn: parent
            text: root.value
            color: root.held ? "#0A1B1B" : "#E7EFF0"
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
