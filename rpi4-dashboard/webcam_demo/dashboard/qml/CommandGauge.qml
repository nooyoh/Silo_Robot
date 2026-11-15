import QtQuick

Item {
    id: root

    required property string title
    property int value: 0
    property bool verticalInput: true
    property bool held: false
    property color accent: "#54D2B1"
    signal changed(int value)

    implicitWidth: 108
    implicitHeight: 166

    function setFromPoint(pointX, pointY) {
        const raw = verticalInput ? 1 - pointY / height * 2 : pointX / width * 2 - 1
        value = Math.max(-100, Math.min(100, Math.round(raw * 100)))
        changed(value)
    }

    function reset() {
        held = false
        if (value !== 0) {
            value = 0
            changed(0)
        }
    }

    Canvas {
        id: dial
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        width: 104
        height: 104
        antialiasing: true

        onPaint: {
            const ctx = getContext("2d")
            const cx = width / 2
            const cy = height / 2
            const radius = 42
            const start = Math.PI * 0.75
            const sweep = Math.PI * 1.5
            ctx.clearRect(0, 0, width, height)
            ctx.lineCap = "butt"

            ctx.beginPath()
            ctx.arc(cx, cy, radius, start, start + sweep, false)
            ctx.strokeStyle = "#354248"
            ctx.lineWidth = 4
            ctx.stroke()

            for (let i = 0; i <= 20; ++i) {
                const angle = start + sweep * i / 20
                const outer = radius + 7
                const inner = outer - (i % 5 === 0 ? 7 : 4)
                ctx.beginPath()
                ctx.moveTo(cx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner)
                ctx.lineTo(cx + Math.cos(angle) * outer, cy + Math.sin(angle) * outer)
                ctx.strokeStyle = i % 5 === 0 ? "#99A7AB" : "#536166"
                ctx.lineWidth = 1
                ctx.stroke()
            }

            const normalized = (root.value + 100) / 200
            const pointer = start + sweep * normalized
            ctx.beginPath()
            ctx.arc(cx, cy, radius, start, pointer, false)
            ctx.strokeStyle = root.held ? root.accent : "#607075"
            ctx.lineWidth = 4
            ctx.stroke()

            ctx.beginPath()
            ctx.moveTo(cx, cy)
            ctx.lineTo(cx + Math.cos(pointer) * (radius - 10), cy + Math.sin(pointer) * (radius - 10))
            ctx.strokeStyle = root.held ? root.accent : "#B7C3C6"
            ctx.lineWidth = 2
            ctx.stroke()
            ctx.beginPath()
            ctx.arc(cx, cy, 4, 0, Math.PI * 2, false)
            ctx.fillStyle = root.held ? root.accent : "#B7C3C6"
            ctx.fill()
        }

        Connections {
            target: root
            function onValueChanged() { dial.requestPaint() }
            function onHeldChanged() { dial.requestPaint() }
        }
    }

    Text {
        anchors.top: dial.bottom
        anchors.topMargin: 5
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.title
        color: root.held ? root.accent : "#B9C5C8"
        font.family: "DejaVu Sans Mono"
        font.pixelSize: 11
        font.bold: true
        font.letterSpacing: 1.3
    }

    Text {
        anchors.top: dial.top
        anchors.topMargin: 39
        anchors.horizontalCenter: dial.horizontalCenter
        text: root.value > 0 ? "+" + root.value : root.value
        color: "#EFF4F4"
        font.family: "DejaVu Sans Mono"
        font.pixelSize: 21
        font.bold: true
    }

    Text {
        anchors.top: dial.top
        anchors.topMargin: 64
        anchors.horizontalCenter: dial.horizontalCenter
        text: "COMMAND %"
        color: "#7D8B90"
        font.family: "DejaVu Sans Mono"
        font.pixelSize: 7
        font.bold: true
        font.letterSpacing: 0.8
    }

    Text {
        anchors.top: dial.bottom
        anchors.topMargin: 27
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.verticalInput ? "FWD  /  REV" : "LEFT / RIGHT"
        color: "#657379"
        font.family: "DejaVu Sans Mono"
        font.pixelSize: 8
    }

    MultiPointTouchArea {
        anchors.fill: parent
        minimumTouchPoints: 1
        maximumTouchPoints: 1
        touchPoints: [TouchPoint { id: touchPoint }]
        onPressed: {
            root.held = true
            root.setFromPoint(touchPoint.x, touchPoint.y)
        }
        onUpdated: root.setFromPoint(touchPoint.x, touchPoint.y)
        onReleased: root.reset()
        onCanceled: root.reset()
    }
}
