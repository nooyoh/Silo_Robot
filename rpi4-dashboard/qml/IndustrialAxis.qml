import QtQuick

Item {
    id: root
    property bool vertical: true
    property string title: "구동"
    property string technicalLabel: "DRIVE"
    property int value: 0
    property bool held: false
    property color activeColor: "#A88A54"
    signal changed(int value)

    function setFromPoint(x, y) {
        const span = vertical ? track.height : track.width
        const point = vertical ? y - track.y : x - track.x
        let normalized = Math.max(0, Math.min(1, point / span))
        if (vertical)
            normalized = 1 - normalized
        value = Math.round(normalized * 200 - 100)
        changed(value)
    }
    function reset() {
        held = false
        if (value !== 0) { value = 0; changed(0) }
    }

    Rectangle { anchors.fill: parent; color: "#292724"; border.color: "#5A564E"; border.width: 1 }
    Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.top: parent.top; anchors.topMargin: 10; text: root.title; color: "#F2EEE5"; font.family: "Noto Sans CJK KR"; font.pixelSize: 14; font.bold: true }
    Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.top: parent.top; anchors.topMargin: 30; text: root.technicalLabel; color: "#9B968B"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true; font.letterSpacing: 1.2 }
    Text { anchors.right: parent.right; anchors.rightMargin: 12; anchors.top: parent.top; anchors.topMargin: 11; text: root.value > 0 ? "+" + root.value : root.value; color: root.held ? root.activeColor : "#E7E3D9"; font.family: "DejaVu Sans Mono"; font.pixelSize: 20; font.bold: true }
    Text { anchors.right: parent.right; anchors.rightMargin: 12; anchors.top: parent.top; anchors.topMargin: 34; text: "% COMMAND"; color: "#89857B"; font.family: "DejaVu Sans Mono"; font.pixelSize: 7 }

    Item {
        id: track
        x: root.vertical ? Math.round((parent.width - 16) / 2) : 14
        y: root.vertical ? 56 : Math.round((parent.height - 14) / 2) + 11
        width: root.vertical ? 16 : parent.width - 28
        height: root.vertical ? parent.height - 72 : 14
        Rectangle { anchors.centerIn: parent; width: root.vertical ? 4 : parent.width; height: root.vertical ? parent.height : 4; color: "#494740" }
        Repeater {
            model: 11
            Rectangle {
                property bool major: index === 0 || index === 5 || index === 10
                x: root.vertical ? -5 : index * (track.width - 1) / 10
                y: root.vertical ? index * (track.height - 1) / 10 : -5
                width: root.vertical ? 26 : 1; height: root.vertical ? 1 : 26
                color: major ? "#8C887D" : "#5C5952"
            }
        }
        Rectangle {
            x: root.vertical ? -3 : Math.round((root.value + 100) / 200 * (track.width - 1)) - 3
            y: root.vertical ? Math.round((1 - (root.value + 100) / 200) * (track.height - 1)) - 3 : -3
            width: root.vertical ? 22 : 6; height: root.vertical ? 6 : 22
            color: root.held ? root.activeColor : "#D8D1C2"; border.color: "#F4EFE4"; border.width: 1
        }
    }
    Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 8; text: root.vertical ? "전진  ·  후진" : "좌회전  ·  우회전"; color: "#9B968B"; font.family: "Noto Sans CJK KR"; font.pixelSize: 9 }
    MultiPointTouchArea {
        anchors.fill: parent; minimumTouchPoints: 1; maximumTouchPoints: 1; touchPoints: [TouchPoint { id: touchPoint }]
        onPressed: { root.held = true; root.setFromPoint(touchPoint.x, touchPoint.y) }
        onUpdated: root.setFromPoint(touchPoint.x, touchPoint.y)
        onReleased: root.reset()
        onCanceled: root.reset()
    }
}
