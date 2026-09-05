import QtQuick
import QtQuick.Controls
import QtQuick.Shapes
import QtMultimedia

ApplicationWindow {
    id: window
    visible: true
    width: 800; height: 480
    minimumWidth: 800; minimumHeight: 480
    title: "SiloRobot Operator Console"
    color: "#1D1C1A"

    readonly property color shell: "#1D1C1A"
    readonly property color surface: "#292724"
    readonly property color raised: "#34312D"
    readonly property color line: "#5A564E"
    readonly property color muted: "#A19C91"
    readonly property color ink: "#F2EEE5"
    readonly property color safe: "#7EA48A"
    readonly property color amber: "#B38B4D"
    readonly property color danger: "#B64A4F"
    property int throttle: 0
    property int turn: 0
    property bool emergencyLatched: false
    property int leftMotor: Math.max(-100, Math.min(100, throttle + turn))
    property int rightMotor: Math.max(-100, Math.min(100, throttle - turn))
    function sendMotion() { if (!emergencyLatched) dashboard.sendMove(throttle, turn) }

    Timer { interval: 50; running: !window.emergencyLatched && (driveAxis.held || steeringAxis.held); repeat: true; onTriggered: window.sendMotion() }
    Rectangle { anchors.fill: parent; color: shell }

    Rectangle {
        id: topBar
        anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
        height: 44; color: "#282623"; border.color: "#514D46"; border.width: 1
        Row {
            anchors.left: parent.left; anchors.leftMargin: 14; anchors.verticalCenter: parent.verticalCenter; spacing: 9
            Rectangle { width: 8; height: 8; color: dashboard.robotOnline ? safe : "#777269" }
            Text { text: "SILO ROBOT"; color: ink; font.family: "DejaVu Sans"; font.pixelSize: 16; font.bold: true; font.letterSpacing: 1.5 }
            Rectangle { width: 1; height: 19; color: "#656057" }
            Text { text: "원격 운용 콘솔"; color: "#C0BAAE"; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true }
        }
        Row {
            anchors.right: parent.right; anchors.rightMargin: 11; anchors.verticalCenter: parent.verticalCenter; spacing: 6
            Rectangle { width: 58; height: 26; color: raised; border.color: line; border.width: 1; Text { anchors.centerIn: parent; text: "수동"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 10; font.bold: true } }
            Rectangle { width: 76; height: 26; color: raised; border.color: line; border.width: 1; Text { anchors.centerIn: parent; text: dashboard.robotOnline ? "로봇 연결" : "로봇 대기"; color: dashboard.robotOnline ? safe : amber; font.family: "Noto Sans CJK KR"; font.pixelSize: 9; font.bold: true } }
            Rectangle { width: 76; height: 26; color: raised; border.color: line; border.width: 1; Text { anchors.centerIn: parent; text: dashboard.orinOnline ? "비전 연결" : "비전 대기"; color: dashboard.orinOnline ? safe : muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 9; font.bold: true } }
            Rectangle { width: 82; height: 26; color: "#3D3933"; border.color: "#777065"; border.width: 1; Text { anchors.centerIn: parent; text: "연결 설정"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 10; font.bold: true } TapHandler { onTapped: connectionPopup.open() } }
        }
    }

    IndustrialAxis {
        id: driveAxis
        anchors.left: parent.left; anchors.leftMargin: 12; anchors.bottom: parent.bottom; anchors.bottomMargin: 10
        width: 210; height: 176; vertical: true; title: "전후진"; technicalLabel: "THROTTLE"; activeColor: amber
        onChanged: function(value) { throttle = value; window.sendMotion() }
    }

    Rectangle {
        id: cameraPanel
        anchors.left: parent.left; anchors.leftMargin: 12; anchors.top: topBar.bottom; anchors.topMargin: 12
        width: 616; height: 226; color: "#171716"; border.color: line; border.width: 1; clip: true

        // 로컬 웹캠 데모 전용 저지연 미리보기 모드. --live-image 로 켜짐 — 실제 배포(RTSP)에는 영향 없음.
        // 파일명에 ?쿼리를 붙이는 캐시버스터는 file:// 스킴에서 안 먹혀서(고정 프레임 문제 재현됨),
        // 대신 두 파일(_a/_b)을 번갈아 읽어 "다른 파일명 = 무조건 새로 읽음"을 보장한다.
        readonly property bool useLiveImage: dashboard.liveImagePath !== ""
        function pingPongPath(path, suffix) {
            const normalized = path.replace(/\\/g, "/")
            const dot = normalized.lastIndexOf(".")
            return dot >= 0 ? normalized.slice(0, dot) + suffix + normalized.slice(dot) : normalized + suffix
        }
        readonly property string liveImagePathA: pingPongPath(dashboard.liveImagePath, "_a")
        readonly property string liveImagePathB: pingPongPath(dashboard.liveImagePath, "_b")
        readonly property bool cameraActive: useLiveImage || dashboard.rtspUrl !== ""
        readonly property real feedX: useLiveImage
            ? liveImage.x + (liveImage.width - liveImage.paintedWidth) / 2
            : videoOutput.contentRect.x
        readonly property real feedY: useLiveImage
            ? liveImage.y + (liveImage.height - liveImage.paintedHeight) / 2
            : cameraHeader.height + videoOutput.contentRect.y
        readonly property real feedW: useLiveImage ? liveImage.paintedWidth : videoOutput.contentRect.width
        readonly property real feedH: useLiveImage ? liveImage.paintedHeight : videoOutput.contentRect.height

        Rectangle {
            id: cameraHeader
            anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right; height: 38
            color: raised; border.color: "#4F4A43"; border.width: 1
            Text { anchors.left: parent.left; anchors.leftMargin: 13; anchors.verticalCenter: parent.verticalCenter; text: "실시간 점검 영상"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 13; font.bold: true }
            Text { anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: dashboard.demoMode ? "데모 모드" : (cameraPanel.cameraActive ? "LIVE" : "CAMERA OFFLINE"); color: dashboard.demoMode ? amber : (cameraPanel.cameraActive ? safe : muted); font.family: dashboard.demoMode ? "Noto Sans CJK KR" : "DejaVu Sans Mono"; font.pixelSize: 9; font.bold: true }
        }
        MediaPlayer { id: player; source: (cameraPanel.useLiveImage || dashboard.rtspUrl === "") ? "" : dashboard.rtspUrl; videoOutput: videoOutput; autoPlay: !cameraPanel.useLiveImage && dashboard.rtspUrl !== "" }
        VideoOutput { id: videoOutput; visible: !cameraPanel.useLiveImage; anchors.top: cameraHeader.bottom; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; fillMode: VideoOutput.PreserveAspectFit }
        Image {
            id: liveImage
            visible: cameraPanel.useLiveImage
            anchors.top: cameraHeader.bottom; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
            fillMode: Image.PreserveAspectFit
            cache: false
            asynchronous: false
            source: cameraPanel.useLiveImage
                ? ("file:///" + (reloadTimer.tick % 2 === 0 ? cameraPanel.liveImagePathA : cameraPanel.liveImagePathB))
                : ""
            Timer {
                id: reloadTimer
                property int tick: 0
                interval: 40
                running: cameraPanel.useLiveImage
                repeat: true
                onTriggered: tick++
            }
        }
        Item {
            visible: !cameraPanel.cameraActive; anchors.top: cameraHeader.bottom; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
            Rectangle { anchors.centerIn: parent; width: 54; height: 38; color: "#302D28"; border.color: "#716A5E"; border.width: 1 }
            Rectangle { anchors.centerIn: parent; width: 16; height: 12; color: "#AAA08D" }
            Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.verticalCenter; anchors.topMargin: 32; text: "카메라 신호를 기다리는 중"; color: "#D0CABE"; font.family: "Noto Sans CJK KR"; font.pixelSize: 13; font.bold: true }
            Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.verticalCenter; anchors.topMargin: 53; text: "RTSP 주소는 연결 설정에서 입력합니다"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 10 }
        }
        Repeater {
            // 세그멘테이션 마스크 윤곽선(polygon). 없으면(구버전 Orin 등) 아무것도 안 그림 —
            // 바운딩박스 Repeater(아래)와 하위호환.
            model: dashboard.detections
            delegate: Shape {
                id: maskShape
                required property var modelData
                x: cameraPanel.feedX
                y: cameraPanel.feedY
                width: cameraPanel.feedW
                height: cameraPanel.feedH
                visible: modelData.polygon !== undefined && modelData.polygon.length > 2
                ShapePath {
                    strokeColor: amber
                    strokeWidth: 2
                    fillColor: Qt.rgba(0.76, 0.64, 0.42, 0.28)
                    PathPolyline {
                        path: {
                            const pts = []
                            const poly = maskShape.modelData.polygon
                            if (poly === undefined)
                                return pts
                            for (const p of poly)
                                pts.push(Qt.point(p.x * maskShape.width, p.y * maskShape.height))
                            return pts
                        }
                    }
                }
            }
        }
        Repeater {
            model: dashboard.detections
            delegate: Item {
                id: detectionBox
                required property var modelData
                x: cameraPanel.feedX + modelData.x * cameraPanel.feedW
                y: cameraPanel.feedY + modelData.y * cameraPanel.feedH
                width: modelData.width * cameraPanel.feedW; height: modelData.height * cameraPanel.feedH
                Rectangle { anchors.fill: parent; color: "transparent"; border.color: amber; border.width: 2 }
                Rectangle { anchors.left: parent.left; anchors.bottom: parent.top; height: 19; width: detectionLabel.width + 14; color: amber }
                Text { id: detectionLabel; anchors.left: parent.left; anchors.leftMargin: 7; anchors.bottom: parent.top; anchors.bottomMargin: 3; text: modelData.label.toUpperCase() + "  " + Math.round(modelData.confidence * 100) + "%"; color: "#241E17"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true }
            }
        }
    }

    Rectangle {
        id: statusPanel
        anchors.left: cameraPanel.right; anchors.leftMargin: 12; anchors.top: cameraPanel.top
        width: 148; height: 226; color: surface; border.color: line; border.width: 1
        Rectangle {
            id: stopButton
            anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 8; height: 56
            color: emergencyLatched ? "#8D3439" : "#5E292D"; border.color: emergencyLatched ? "#F2C1C1" : "#C16D70"; border.width: 1
            Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: 9; text: emergencyLatched ? "정지 유지 중" : "비상 정지"; color: "#FFF5F2"; font.family: "Noto Sans CJK KR"; font.pixelSize: 15; font.bold: true }
            Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 8; text: emergencyLatched ? "다시 눌러 해제" : "E-STOP"; color: "#F1C9C8"; font.family: emergencyLatched ? "Noto Sans CJK KR" : "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true; font.letterSpacing: emergencyLatched ? 0 : 1.1 }
            TapHandler { onTapped: { throttle = 0; turn = 0; emergencyLatched = !emergencyLatched; if (emergencyLatched) dashboard.emergencyStop(); else dashboard.releaseEmergencyStop() } }
        }
        Text { anchors.left: parent.left; anchors.leftMargin: 10; anchors.top: stopButton.bottom; anchors.topMargin: 10; text: "전원"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 10 }
        Text { anchors.right: parent.right; anchors.rightMargin: 10; anchors.top: stopButton.bottom; anchors.topMargin: 8; text: dashboard.battery; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 15; font.bold: true }
        Rectangle { anchors.left: parent.left; anchors.leftMargin: 10; anchors.right: parent.right; anchors.rightMargin: 10; anchors.top: stopButton.bottom; anchors.topMargin: 31; height: 4; color: "#4B4841"; Rectangle { width: parent.width * 0.72; height: parent.height; color: safe } }
        Rectangle { anchors.left: parent.left; anchors.leftMargin: 10; anchors.right: parent.right; anchors.rightMargin: 10; anchors.top: stopButton.bottom; anchors.topMargin: 48; height: 1; color: line }
        Text { anchors.left: parent.left; anchors.leftMargin: 10; anchors.top: stopButton.bottom; anchors.topMargin: 60; text: "자세  R " + dashboard.roll + "  P " + dashboard.pitch; color: "#D8D3C8"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true }
        Rectangle { anchors.left: parent.left; anchors.leftMargin: 10; anchors.right: parent.right; anchors.rightMargin: 10; anchors.bottom: parent.bottom; anchors.bottomMargin: 10; height: 30; color: dashboard.robotOnline ? "#334239" : "#39352D"; border.color: dashboard.robotOnline ? safe : "#7B6845"; border.width: 1 }
        Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 19; text: dashboard.robotOnline ? "로봇 통신 정상" : "로봇 연결 대기"; color: dashboard.robotOnline ? "#D4E4D8" : "#E0C995"; font.family: "Noto Sans CJK KR"; font.pixelSize: 9; font.bold: true }
    }

    Rectangle {
        id: footer
        anchors.left: driveAxis.right; anchors.leftMargin: 12; anchors.bottom: parent.bottom; anchors.bottomMargin: 10
        width: 332; height: 176
        color: surface; border.color: line; border.width: 1
        Column {
            anchors.left: parent.left; anchors.leftMargin: 14; anchors.top: parent.top; anchors.topMargin: 13; anchors.right: parent.right; anchors.rightMargin: 14; spacing: 8
            Text { text: "운용 상태"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 14; font.bold: true }
            Text { text: emergencyLatched ? "비상 정지 유지 중" : (dashboard.demoMode ? "데모 모드 · 통신 확인" : dashboard.connectionSummary); color: emergencyLatched ? "#E4A7A7" : (dashboard.demoMode ? "#D9C18C" : safe); font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true }
            Rectangle { width: parent.width; height: 1; color: line }
            Row {
                spacing: 18
                Column { spacing: 4; Text { text: "좌측 모터"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 9 } Text { text: (leftMotor > 0 ? "+" : "") + leftMotor + "%"; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 16; font.bold: true } }
                Column { spacing: 4; Text { text: "우측 모터"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 9 } Text { text: (rightMotor > 0 ? "+" : "") + rightMotor + "%"; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 16; font.bold: true } }
                Column { spacing: 4; Text { text: "비전"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 9 } Text { text: dashboard.orinOnline ? "ONLINE" : "STANDBY"; color: dashboard.orinOnline ? safe : muted; font.family: "DejaVu Sans Mono"; font.pixelSize: 11; font.bold: true } }
            }
            Rectangle { width: parent.width; height: 1; color: line }
            Text { text: "거리  L " + dashboard.distances[0] + "   C " + dashboard.distances[1] + "   R " + dashboard.distances[2]; color: "#D8D3C8"; font.family: "DejaVu Sans Mono"; font.pixelSize: 9; font.bold: true }
        }
    }

    IndustrialAxis {
        id: steeringAxis
        anchors.left: footer.right; anchors.leftMargin: 12; anchors.bottom: parent.bottom; anchors.bottomMargin: 10
        width: 210; height: 176; vertical: false; title: "좌우 조향"; technicalLabel: "STEERING"; activeColor: amber
        onChanged: function(value) { turn = value; window.sendMotion() }
    }

    Popup {
        id: connectionPopup
        modal: true; focus: true; anchors.centerIn: Overlay.overlay; width: 760; height: 470; padding: 0
        onOpened: { dashboardHostField.text = dashboard.advertisedHost; rtspField.text = dashboard.rtspUrl; websocketPortField.text = dashboard.websocketPort; connectionFeedback.text = "저장된 연결 정보를 불러왔습니다."; connectionFeedback.color = muted; touchKeyboard.targetField = null }
        background: Rectangle { color: "#2A2825"; border.color: "#777066"; border.width: 1 }
        contentItem: Item {
            anchors.fill: parent
            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 52; color: "#36332E"; border.color: line; border.width: 1 }
            Text { anchors.left: parent.left; anchors.leftMargin: 18; anchors.top: parent.top; anchors.topMargin: 12; text: "연결 설정"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 17; font.bold: true }
            Text { anchors.left: parent.left; anchors.leftMargin: 18; anchors.top: parent.top; anchors.topMargin: 34; text: "CONNECTION CONFIGURATION"; color: muted; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true; font.letterSpacing: 1.1 }
            Text { anchors.right: parent.right; anchors.rightMargin: 16; anchors.top: parent.top; anchors.topMargin: 8; text: "×"; color: "#E4DED3"; font.pixelSize: 27; TapHandler { onTapped: connectionPopup.close() } }
            Column {
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.leftMargin: 18; anchors.rightMargin: 18; anchors.topMargin: 60; spacing: 7
                Column { spacing: 4; Text { text: "대시보드 Tailscale 주소"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true } TextField { id: dashboardHostField; width: parent.width; height: 31; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 12; placeholderText: "예: 100.74.141.112"; placeholderTextColor: muted; selectByMouse: true; onActiveFocusChanged: if (activeFocus) touchKeyboard.activate(dashboardHostField); background: Rectangle { color: "#1B1A18"; border.color: dashboardHostField.activeFocus ? "#C3A36A" : line; border.width: 1 } } }
                Column { spacing: 4; Text { text: "카메라 RTSP 주소"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true } TextField { id: rtspField; width: parent.width; height: 31; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 12; placeholderText: "rtsp://<nano-ip>:8554/robot"; placeholderTextColor: muted; selectByMouse: true; onActiveFocusChanged: if (activeFocus) touchKeyboard.activate(rtspField); background: Rectangle { color: "#1B1A18"; border.color: rtspField.activeFocus ? "#C3A36A" : line; border.width: 1 } } }
                Row { spacing: 16; Column { spacing: 4; Text { text: "WebSocket 포트"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true } TextField { id: websocketPortField; width: 180; height: 31; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 12; inputMethodHints: Qt.ImhDigitsOnly; selectByMouse: true; onActiveFocusChanged: if (activeFocus) touchKeyboard.activate(websocketPortField); background: Rectangle { color: "#1B1A18"; border.color: websocketPortField.activeFocus ? "#C3A36A" : line; border.width: 1 } } } Column { spacing: 5; Text { text: "Nano / Orin 접속점"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 10; font.bold: true } Text { text: dashboard.dashboardEndpoint; color: "#DCC69A"; font.family: "DejaVu Sans Mono"; font.pixelSize: 11; font.bold: true } } }
                Text { id: connectionFeedback; font.family: "Noto Sans CJK KR"; font.pixelSize: 10 }
            }

            Item {
                id: touchKeyboard
                anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                anchors.leftMargin: 18; anchors.rightMargin: 18
                height: 178
                property var targetField: null

                function activate(field) {
                    targetField = field
                }
                function addText(text) {
                    if (!targetField)
                        return
                    const start = Math.min(targetField.selectionStart, targetField.selectionEnd)
                    const end = Math.max(targetField.selectionStart, targetField.selectionEnd)
                    if (start !== end) {
                        targetField.remove(start, end)
                        targetField.cursorPosition = start
                    }
                    targetField.insert(targetField.cursorPosition, text)
                    targetField.cursorPosition += text.length
                    targetField.forceActiveFocus()
                }
                function backspace() {
                    if (!targetField)
                        return
                    const start = Math.min(targetField.selectionStart, targetField.selectionEnd)
                    const end = Math.max(targetField.selectionStart, targetField.selectionEnd)
                    if (start !== end) {
                        targetField.remove(start, end)
                        targetField.cursorPosition = start
                    } else if (targetField.cursorPosition > 0) {
                        const position = targetField.cursorPosition
                        targetField.remove(position - 1, position)
                        targetField.cursorPosition = position - 1
                    }
                    targetField.forceActiveFocus()
                }
                function finish() {
                    if (targetField)
                        targetField.focus = false
                    targetField = null
                }

                Rectangle { anchors.fill: parent; color: "#211F1C"; border.color: "#625C52"; border.width: 1 }
                Text { anchors.left: parent.left; anchors.leftMargin: 11; anchors.top: parent.top; anchors.topMargin: 7; text: touchKeyboard.targetField ? "터치 키보드  ·  URL / IP / PORT" : "입력할 항목을 누르세요"; color: touchKeyboard.targetField ? "#DCC69A" : muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 9; font.bold: true }
                Column {
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.leftMargin: 10; anchors.rightMargin: 10; anchors.topMargin: 28; spacing: 5
                    Row {
                        width: parent.width; property int keyCount: 12; spacing: 5
                        Repeater {
                            model: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", ".", "⌫"]
                            delegate: Rectangle {
                                width: (parent.width - (parent.keyCount - 1) * 5) / parent.keyCount; height: 29
                                color: modelData === "⌫" ? "#56413A" : "#35312C"; border.color: "#6A6358"; border.width: 1
                                Text { anchors.centerIn: parent; text: modelData; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 11; font.bold: true }
                                TapHandler { onTapped: modelData === "⌫" ? touchKeyboard.backspace() : touchKeyboard.addText(modelData) }
                            }
                        }
                    }
                    Row {
                        width: parent.width; property int keyCount: 11; spacing: 5
                        Repeater {
                            model: ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "@"]
                            delegate: Rectangle {
                                width: (parent.width - (parent.keyCount - 1) * 5) / parent.keyCount; height: 29
                                color: "#35312C"; border.color: "#6A6358"; border.width: 1
                                Text { anchors.centerIn: parent; text: modelData; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 11; font.bold: true }
                                TapHandler { onTapped: touchKeyboard.addText(modelData) }
                            }
                        }
                    }
                    Row {
                        width: parent.width; property int keyCount: 12; spacing: 5
                        Repeater {
                            model: ["a", "s", "d", "f", "g", "h", "j", "k", "l", ":", "/", "_"]
                            delegate: Rectangle {
                                width: (parent.width - (parent.keyCount - 1) * 5) / parent.keyCount; height: 29
                                color: "#35312C"; border.color: "#6A6358"; border.width: 1
                                Text { anchors.centerIn: parent; text: modelData; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 11; font.bold: true }
                                TapHandler { onTapped: touchKeyboard.addText(modelData) }
                            }
                        }
                    }
                    Row {
                        width: parent.width; property int keyCount: 12; spacing: 5
                        Repeater {
                            model: ["z", "x", "c", "v", "b", "n", "m", "-", "+", " ", "완료", "⌫"]
                            delegate: Rectangle {
                                width: (parent.width - (parent.keyCount - 1) * 5) / parent.keyCount; height: 29
                                color: modelData === "완료" ? "#7D6842" : (modelData === "⌫" ? "#56413A" : "#35312C"); border.color: modelData === "완료" ? "#D3B77A" : "#6A6358"; border.width: 1
                                Text { anchors.centerIn: parent; text: modelData === " " ? "SPACE" : modelData; color: ink; font.family: modelData === "완료" ? "Noto Sans CJK KR" : "DejaVu Sans Mono"; font.pixelSize: modelData === " " ? 8 : 10; font.bold: true }
                                TapHandler { onTapped: { if (modelData === "완료") touchKeyboard.finish(); else if (modelData === "⌫") touchKeyboard.backspace(); else touchKeyboard.addText(modelData) } }
                            }
                        }
                    }
                }
            }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 18; anchors.bottom: parent.bottom; anchors.bottomMargin: 190; spacing: 8
                Button { text: "취소"; onClicked: connectionPopup.close(); contentItem: Text { text: parent.text; color: "#E3DDD2"; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter } background: Rectangle { color: "#413D37"; border.color: line; border.width: 1 } }
                Button { text: "저장 및 적용"; onClicked: { const port = Number(websocketPortField.text); if (dashboard.saveConnectionSettings(dashboardHostField.text, rtspField.text, port)) { connectionFeedback.text = "저장했습니다. 새 연결 설정을 적용합니다."; connectionFeedback.color = safe } else { connectionFeedback.text = "저장하지 못했습니다. 주소와 포트를 확인하세요."; connectionFeedback.color = "#E69A9B" } } contentItem: Text { text: parent.text; color: "#211D18"; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter } background: Rectangle { color: "#C3A36A"; border.color: "#E9D4A4"; border.width: 1 } }
            }
        }
    }
}
