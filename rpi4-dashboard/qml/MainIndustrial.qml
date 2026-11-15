import QtQuick
import QtQuick.Controls
import QtQuick.Shapes
import QtMultimedia

ApplicationWindow {
    id: window
    visible: true
    flags: Qt.FramelessWindowHint
    x: 0; y: 0
    width: 800; height: 480
    minimumWidth: 800; minimumHeight: 480
    title: "SiloRobot Operator Console"
    color: "#1D1C1A"
    // 창이 처음 키보드 포커스를 받는 순간(=사용자가 아무 버튼이나 처음 누르는 순간) squeekboard가
    // "이 창엔 입력창이 있다"고 판단해 자동으로 떠버린다. 시작하자마자 명시적으로 숨겨서, 이후로는
    // TextField 포커스에 맞춘 우리 쪽 대칭 제어만 적용되게 한다.
    Component.onCompleted: dashboard.setOnScreenKeyboardVisible(false)

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
    property bool stopRequested: false
    property bool captureInProgress: false
    readonly property bool emergencyLatched: stopRequested || dashboard.safetyLatched
    property int leftMotor: Math.max(-100, Math.min(100, throttle + turn))
    property int rightMotor: Math.max(-100, Math.min(100, throttle - turn))
    function sendMotion() { if (!emergencyLatched) dashboard.sendMove(throttle, turn) }
    function safetyColor(state) { return state === "NORMAL" ? safe : (state === "WARNING" ? amber : (state === "STOPPED" ? danger : "#777269")) }
    function captureInspectionFrame(trigger) {
        const recordTrigger = trigger || "OPERATOR"
        if (captureInProgress) {
            dashboard.saveInspectionRecord("", "다른 이미지 캡처가 진행 중입니다.", recordTrigger)
            return
        }
        if (dashboard.rtspUrl === "") { dashboard.saveInspectionRecord("", "수신 중인 실제 영상 프레임이 없습니다.", recordTrigger); return }
        captureInProgress = true
        const accepted = captureFrame.grabToImage(function(result) {
            if (!result || !result.saveToFile(dashboard.captureStagingPath()))
                dashboard.saveInspectionRecord("", "영상 프레임 캡처에 실패했습니다.", recordTrigger)
            else
                dashboard.saveInspectionRecord(dashboard.captureStagingPath(), "", recordTrigger)
            captureInProgress = false
        })
        if (!accepted) {
            captureInProgress = false
            dashboard.saveInspectionRecord("", "영상 캡처 요청을 시작하지 못했습니다.", recordTrigger)
        }
    }
    Connections {
        target: dashboard
        function onSafetyChanged() {
            if (dashboard.safetyLatched)
                window.stopRequested = false
        }
        function onSafetyRecordRequested(trigger) {
            window.captureInspectionFrame(trigger)
        }
    }

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
            Rectangle { width: 58; height: 26; color: raised; border.color: line; border.width: 1; Text { anchors.centerIn: parent; text: "계획"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 10; font.bold: true } TapHandler { onTapped: missionPopup.open() } }
            Rectangle { width: 58; height: 26; color: "#3D3933"; border.color: "#777065"; border.width: 1; Text { anchors.centerIn: parent; text: "점검 기록"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 9; font.bold: true } TapHandler { onTapped: window.captureInspectionFrame() } }
            Rectangle { width: 58; height: 26; color: "#3D3933"; border.color: "#777065"; border.width: 1; Text { anchors.centerIn: parent; text: "기록 보기"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 9; font.bold: true } TapHandler { onTapped: { recordsPopup.refresh(); recordsPopup.selectedIndex = 0; recordsPopup.expanded = false; recordsPopup.open() } } }
            Rectangle { width: 76; height: 26; color: raised; border.color: line; border.width: 1; Text { anchors.centerIn: parent; text: dashboard.robotOnline ? "로봇 연결" : "로봇 대기"; color: dashboard.robotOnline ? safe : amber; font.family: "Noto Sans CJK KR"; font.pixelSize: 9; font.bold: true } }
            Rectangle { width: 76; height: 26; color: raised; border.color: line; border.width: 1; Text { anchors.centerIn: parent; text: dashboard.orinOnline ? "비전 연결" : "비전 대기"; color: dashboard.orinOnline ? safe : muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 9; font.bold: true } }
            Rectangle { width: 82; height: 26; color: "#3D3933"; border.color: "#777065"; border.width: 1; Text { anchors.centerIn: parent; text: "연결 설정"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 10; font.bold: true } TapHandler { onTapped: connectionPopup.open() } }
            Rectangle { width: 58; height: 26; color: "#4A2E2E"; border.color: "#8A5A5A"; border.width: 1; Text { anchors.centerIn: parent; text: "종료"; color: "#F0D8D8"; font.family: "Noto Sans CJK KR"; font.pixelSize: 10; font.bold: true } TapHandler { onTapped: quitPopup.open() } }
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
        Rectangle {
            id: cameraHeader
            anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right; height: 38
            color: raised; border.color: "#4F4A43"; border.width: 1
            Text { anchors.left: parent.left; anchors.leftMargin: 13; anchors.verticalCenter: parent.verticalCenter; text: "실시간 점검 영상"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 13; font.bold: true }
            Rectangle {
                anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                width: 54; height: 22; color: "#3D3933"; border.color: "#777065"; border.width: 1
                Text { anchors.centerIn: parent; text: "재연결"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 8; font.bold: true }
                TapHandler { onTapped: { player.stop(); player.play() } }
            }
            Text { anchors.right: parent.right; anchors.rightMargin: 72; anchors.verticalCenter: parent.verticalCenter; text: dashboard.demoMode ? "데모 모드" : (dashboard.rtspUrl === "" ? "CAMERA OFFLINE" : "LIVE"); color: dashboard.demoMode ? amber : (dashboard.rtspUrl === "" ? muted : safe); font.family: dashboard.demoMode ? "Noto Sans CJK KR" : "DejaVu Sans Mono"; font.pixelSize: 9; font.bold: true }
        }
        MediaPlayer { id: player; source: dashboard.rtspUrl === "" ? "" : dashboard.rtspUrl; videoOutput: videoOutput; autoPlay: dashboard.rtspUrl !== "" }
        // 앱이 뜬 시점에 나노 B01의 RTSP 서버가 아직 준비 안 됐으면 첫 연결 시도가 조용히
        // 실패한 채로 멈춰 있을 수 있다. 자동 주기 재시도는 화면이 계속 깜빡여서(정상 재생
        // 중에도 매 주기 끊겼다 재생됨) 사용자 요청으로 제거 — 대신 "재연결" 버튼을 눌러 직접
        // 재시도한다.
        // 영상과 결함 박스를 한 아이템에 같이 두면, 점검 기록 캡처 시 박스가 찍힌 화면 그대로
        // 저장할 수 있다(캡처는 이 아이템을 grabToImage한다).
        Item {
            id: captureFrame
            anchors.top: cameraHeader.bottom; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
            VideoOutput { id: videoOutput; anchors.fill: parent; fillMode: VideoOutput.PreserveAspectFit }
            Repeater {
                model: dashboard.detections
                delegate: Item {
                    id: detectionBox
                    required property var modelData
                    x: videoOutput.contentRect.x + modelData.x * videoOutput.contentRect.width
                    y: videoOutput.contentRect.y + modelData.y * videoOutput.contentRect.height
                    width: modelData.width * videoOutput.contentRect.width; height: modelData.height * videoOutput.contentRect.height
                    Rectangle { anchors.fill: parent; color: "transparent"; border.color: amber; border.width: 2 }
                    Rectangle { anchors.left: parent.left; anchors.bottom: parent.top; height: 19; width: detectionLabel.width + 14; color: amber }
                    Text { id: detectionLabel; anchors.left: parent.left; anchors.leftMargin: 7; anchors.bottom: parent.top; anchors.bottomMargin: 3; text: modelData.label.toUpperCase() + "  " + Math.round(modelData.confidence * 100) + "%"; color: "#241E17"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true }
                }
            }
        }
        Item {
            visible: dashboard.rtspUrl === ""; anchors.top: cameraHeader.bottom; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
            Rectangle { anchors.centerIn: parent; width: 54; height: 38; color: "#302D28"; border.color: "#716A5E"; border.width: 1 }
            Rectangle { anchors.centerIn: parent; width: 16; height: 12; color: "#AAA08D" }
            Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.verticalCenter; anchors.topMargin: 32; text: "카메라 신호를 기다리는 중"; color: "#D0CABE"; font.family: "Noto Sans CJK KR"; font.pixelSize: 13; font.bold: true }
            Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.verticalCenter; anchors.topMargin: 53; text: "RTSP 주소는 연결 설정에서 입력합니다"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 10 }
        }
        Rectangle {
            anchors.left: parent.left; anchors.leftMargin: 8; anchors.bottom: parent.bottom; anchors.bottomMargin: 8; width: 178; height: 48
            color: "#24231FDD"; border.color: "#6A6358"; border.width: 1
            Image { anchors.left: parent.left; anchors.leftMargin: 5; anchors.verticalCenter: parent.verticalCenter; width: 54; height: 36; fillMode: Image.PreserveAspectCrop; source: dashboard.recentRecords.length && dashboard.recentRecords[0].saved ? dashboard.recentRecords[0].image : ""; visible: source !== "" }
            Text { anchors.left: parent.left; anchors.leftMargin: 65; anchors.right: parent.right; anchors.rightMargin: 5; anchors.top: parent.top; anchors.topMargin: 7; text: dashboard.recentRecords.length ? "최근 기록 " + dashboard.recentRecords[0].time : "최근 점검 기록 없음"; color: ink; elide: Text.ElideRight; font.family: "Noto Sans CJK KR"; font.pixelSize: 8; font.bold: true }
            Text { anchors.left: parent.left; anchors.leftMargin: 65; anchors.right: parent.right; anchors.rightMargin: 5; anchors.top: parent.top; anchors.topMargin: 25; text: dashboard.recordFeedback; color: dashboard.recentRecords.length && dashboard.recentRecords[0].saved ? safe : amber; elide: Text.ElideRight; font.family: "Noto Sans CJK KR"; font.pixelSize: 7 }
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
            TapHandler { onTapped: { throttle = 0; turn = 0; if (emergencyLatched) dashboard.releaseEmergencyStop(); else { stopRequested = true; dashboard.emergencyStop() } } }
        }
        Rectangle { anchors.left: parent.left; anchors.leftMargin: 10; anchors.right: parent.right; anchors.rightMargin: 10; anchors.top: stopButton.bottom; anchors.topMargin: 9; height: 24; color: "#252421"; border.color: window.safetyColor(dashboard.safetyState); border.width: 1
            Text { anchors.centerIn: parent; text: "안전 " + dashboard.safetyState; color: window.safetyColor(dashboard.safetyState); font.family: "DejaVu Sans Mono"; font.pixelSize: 10; font.bold: true }
        }
        Text { anchors.left: parent.left; anchors.leftMargin: 10; anchors.top: stopButton.bottom; anchors.topMargin: 40; text: dashboard.safetyReasons.length ? dashboard.safetyReasons.join(" · ") : "안전 사유 없음"; color: dashboard.safetyReasons.length ? "#E1C78E" : safe; width: parent.width - 20; elide: Text.ElideRight; font.family: "Noto Sans CJK KR"; font.pixelSize: 8; font.bold: true }
        Text { anchors.left: parent.left; anchors.leftMargin: 10; anchors.top: stopButton.bottom; anchors.topMargin: 57; text: "전원 " + dashboard.battery; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 10; font.bold: true }
        Text { anchors.left: parent.left; anchors.leftMargin: 10; anchors.top: stopButton.bottom; anchors.topMargin: 74; text: "R " + dashboard.roll + "  P " + dashboard.pitch + "  Y " + dashboard.yaw; color: "#D8D3C8"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true }
        Text { anchors.left: parent.left; anchors.leftMargin: 10; anchors.top: stopButton.bottom; anchors.topMargin: 91; text: dashboard.safetyArmed ? "자동정지 감시 활성" : "모니터링 전용 — 자동정지 비활성"; color: dashboard.safetyArmed ? safe : amber; width: parent.width - 20; elide: Text.ElideRight; font.family: "Noto Sans CJK KR"; font.pixelSize: 8; font.bold: true }
        Text { anchors.left: parent.left; anchors.leftMargin: 10; anchors.top: stopButton.bottom; anchors.topMargin: 108; text: dashboard.releaseFeedback; color: danger; width: parent.width - 20; elide: Text.ElideRight; font.family: "Noto Sans CJK KR"; font.pixelSize: 8; font.bold: true }
        Rectangle { anchors.left: parent.left; anchors.leftMargin: 10; anchors.right: parent.right; anchors.rightMargin: 10; anchors.bottom: parent.bottom; anchors.bottomMargin: 10; height: 24; color: dashboard.robotOnline ? "#334239" : "#39352D"; border.color: dashboard.robotOnline ? safe : "#7B6845"; border.width: 1 }
        Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 17; text: dashboard.robotOnline ? "로봇 통신 정상" : "로봇 연결 대기"; color: dashboard.robotOnline ? "#D4E4D8" : "#E0C995"; font.family: "Noto Sans CJK KR"; font.pixelSize: 8; font.bold: true }
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
            Text { text: "거리(" + dashboard.distanceUnit + ")  L " + dashboard.distances[0] + "  C " + dashboard.distances[1] + "  R " + dashboard.distances[2]; color: "#D8D3C8"; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true }
            Text { text: "평균 " + dashboard.distanceMean + "  ·  편차 " + dashboard.distanceSpread; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 8 }
        }
    }

    IndustrialAxis {
        id: steeringAxis
        anchors.left: footer.right; anchors.leftMargin: 12; anchors.bottom: parent.bottom; anchors.bottomMargin: 10
        width: 210; height: 176; vertical: false; title: "좌우 조향"; technicalLabel: "STEERING"; activeColor: amber
        onChanged: function(value) { turn = value; window.sendMotion() }
    }

    Popup {
        id: quitPopup
        modal: true; focus: true; anchors.centerIn: Overlay.overlay; width: 320; height: 160; padding: 0
        background: Rectangle { color: "#2A2825"; border.color: "#777066"; border.width: 1 }
        contentItem: Item {
            anchors.fill: parent
            MouseArea { anchors.fill: parent }
            Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: 20; text: "대시보드 앱을 종료할까요?"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 13; font.bold: true }
            Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: 46; text: "전체화면이라 창 닫기 버튼이 없습니다"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 9 }
            Row {
                anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 20; spacing: 10
                Rectangle { width: 110; height: 34; color: "#413D37"; border.color: line; border.width: 1
                    Text { anchors.centerIn: parent; text: "취소"; color: "#E3DDD2"; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true }
                    TapHandler { onTapped: quitPopup.close() }
                }
                Rectangle { width: 110; height: 34; color: "#8D3439"; border.color: "#C16D70"; border.width: 1
                    Text { anchors.centerIn: parent; text: "종료"; color: "#FFF5F2"; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true }
                    TapHandler { onTapped: dashboard.quitApplication() }
                }
            }
        }
    }

    Popup {
        id: deleteConfirmPopup
        modal: true; focus: true; anchors.centerIn: Overlay.overlay; width: 320; height: 160; padding: 0
        background: Rectangle { color: "#2A2825"; border.color: "#777066"; border.width: 1 }
        contentItem: Item {
            anchors.fill: parent
            MouseArea { anchors.fill: parent }
            Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: 20; text: "이 점검 기록을 삭제할까요?"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 13; font.bold: true }
            Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: 46; text: recordsPopup.current ? recordsPopup.current.recordId : ""; color: muted; font.family: "DejaVu Sans Mono"; font.pixelSize: 9 }
            Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: 62; text: "이미지와 기록이 함께 삭제되며 되돌릴 수 없습니다"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 9 }
            Row {
                anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 20; spacing: 10
                Rectangle { width: 110; height: 34; color: "#413D37"; border.color: line; border.width: 1
                    Text { anchors.centerIn: parent; text: "취소"; color: "#E3DDD2"; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true }
                    TapHandler { onTapped: deleteConfirmPopup.close() }
                }
                Rectangle { width: 110; height: 34; color: "#8D3439"; border.color: "#C16D70"; border.width: 1
                    Text { anchors.centerIn: parent; text: "삭제"; color: "#FFF5F2"; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true }
                    TapHandler {
                        onTapped: {
                            if (recordsPopup.current)
                                dashboard.deleteRecord(recordsPopup.current.date, recordsPopup.current.recordId)
                            deleteConfirmPopup.close()
                            recordsPopup.refresh()
                        }
                    }
                }
            }
        }
    }

    Popup {
        id: recordsPopup
        modal: true; focus: true
        x: (Overlay.overlay.width - width) / 2; y: 2
        width: 780; height: 440; padding: 0
        onOpened: dashboard.setOnScreenKeyboardVisible(false)
        property var entries: []
        property int selectedIndex: 0
        property bool expanded: false
        readonly property var current: entries.length > selectedIndex ? entries[selectedIndex] : null
        function refresh() {
            entries = dashboard.loadAllRecords()
            if (selectedIndex >= entries.length) selectedIndex = 0
        }
        background: Rectangle { color: "#24231F"; border.color: line; border.width: 1 }
        contentItem: Item {
            anchors.fill: parent
            MouseArea { anchors.fill: parent }
            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 48; color: raised
                Text { anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter; text: "점검 기록 보기 · " + recordsPopup.entries.length + "건"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 16; font.bold: true }
                Row {
                    anchors.right: parent.right; anchors.rightMargin: 50; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                    visible: recordsPopup.current !== null
                    Rectangle {
                        width: 62; height: 26; color: "#3D3933"; border.color: "#777065"; border.width: 1
                        Text { anchors.centerIn: parent; text: recordsPopup.expanded ? "간단히" : "더보기"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 9; font.bold: true }
                        TapHandler { onTapped: recordsPopup.expanded = !recordsPopup.expanded }
                    }
                    Rectangle {
                        width: 62; height: 26; color: "#3D3933"; border.color: "#777065"; border.width: 1
                        Text { anchors.centerIn: parent; text: "삭제"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 9; font.bold: true }
                        TapHandler { onTapped: deleteConfirmPopup.open() }
                    }
                }
                Text { anchors.right: parent.right; anchors.rightMargin: 15; anchors.verticalCenter: parent.verticalCenter; text: "×"; color: ink; font.pixelSize: 24; TapHandler { onTapped: recordsPopup.close() } }
            }
            Rectangle {
                anchors.left: parent.left; anchors.leftMargin: 16; anchors.top: parent.top; anchors.topMargin: 60; anchors.bottom: parent.bottom; anchors.bottomMargin: 16
                width: 190; color: "#171716"; border.color: line; border.width: 1
                Text { visible: recordsPopup.entries.length === 0; anchors.centerIn: parent; anchors.margins: 10; width: parent.width - 20; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter; text: "저장된 점검 기록이 없습니다"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 10 }
                ListView {
                    anchors.fill: parent; anchors.margins: 6; clip: true; spacing: 4
                    model: recordsPopup.entries
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        width: ListView.view.width; height: 54
                        color: index === recordsPopup.selectedIndex ? "#3D3933" : "transparent"
                        border.color: index === recordsPopup.selectedIndex ? "#C3A36A" : "transparent"; border.width: 1
                        Rectangle { anchors.left: parent.left; anchors.leftMargin: 6; anchors.verticalCenter: parent.verticalCenter; width: 40; height: 40; color: "#0D0C0B"
                            Image { anchors.fill: parent; anchors.margins: 1; source: modelData.saved ? modelData.image : ""; fillMode: Image.PreserveAspectCrop; visible: modelData.saved }
                            Text { visible: !modelData.saved; anchors.centerIn: parent; text: "✕"; color: danger; font.pixelSize: 14 }
                        }
                        Column { anchors.left: parent.left; anchors.leftMargin: 52; anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter; spacing: 2
                            Text { text: modelData.date + " " + modelData.time.substring(11, 19); color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 9; elide: Text.ElideRight; width: parent.width }
                            Text { text: modelData.safetyState; color: window.safetyColor(modelData.safetyState); font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true }
                        }
                        TapHandler { onTapped: recordsPopup.selectedIndex = index }
                    }
                }
            }
            Rectangle {
                anchors.left: parent.left; anchors.leftMargin: 218; anchors.right: parent.right; anchors.rightMargin: 16
                anchors.top: parent.top; anchors.topMargin: 60; anchors.bottom: parent.bottom; anchors.bottomMargin: 16
                color: "#0D0C0B"; border.color: line; border.width: 1
                Text { visible: !recordsPopup.current; anchors.centerIn: parent; text: "왼쪽 목록에서 기록을 선택하세요"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 11 }
                Image {
                    id: recordImage
                    visible: recordsPopup.current && recordsPopup.current.saved
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: metaPanel.top
                    anchors.margins: 8
                    source: recordsPopup.current && recordsPopup.current.saved ? recordsPopup.current.image : ""
                    fillMode: Image.PreserveAspectFit
                }
                Text {
                    visible: recordsPopup.current && !recordsPopup.current.saved
                    anchors.centerIn: parent; width: parent.width - 40; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter
                    text: recordsPopup.current ? "이미지 저장 실패: " + recordsPopup.current.imageError : ""
                    color: danger; font.family: "Noto Sans CJK KR"; font.pixelSize: 10
                }
                Rectangle {
                    id: metaPanel; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                    height: recordsPopup.expanded ? 136 : 64; color: "#171716"; border.color: line; border.width: 1
                    Column {
                        anchors.fill: parent; anchors.margins: 10; spacing: 10
                        Row { spacing: 24
                            Column { spacing: 3
                                Text { text: "안전상태"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 8 }
                                Text { text: recordsPopup.current ? recordsPopup.current.safetyState : "--"; color: recordsPopup.current ? window.safetyColor(recordsPopup.current.safetyState) : muted; font.family: "DejaVu Sans Mono"; font.pixelSize: 13; font.bold: true }
                            }
                            Column { spacing: 3
                                Text { text: "자세 R/P/Y"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 8 }
                                Text { text: recordsPopup.current ? (recordsPopup.current.roll + " / " + recordsPopup.current.pitch + " / " + recordsPopup.current.yaw) : "--"; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 11 }
                            }
                            Column { spacing: 3
                                Text { text: "거리"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 8 }
                                Text { text: recordsPopup.current ? recordsPopup.current.distance : "--"; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 11 }
                            }
                            Column { spacing: 3
                                Text { text: "기록 ID"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 8 }
                                Text { text: recordsPopup.current ? recordsPopup.current.recordId : "--"; color: "#DCC69A"; font.family: "DejaVu Sans Mono"; font.pixelSize: 10 }
                            }
                        }
                        Row {
                            spacing: 24; visible: recordsPopup.expanded
                            Column { spacing: 3
                                Text { text: "위치(전개도 pose)"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 8 }
                                Text { text: recordsPopup.current && recordsPopup.current.pose ? recordsPopup.current.pose + " (" + recordsPopup.current.poseSource + ")" : "--"; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 10 }
                            }
                            Column { spacing: 3
                                Text { text: "계획/웨이포인트"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 8 }
                                Text { text: recordsPopup.current && recordsPopup.current.planId ? recordsPopup.current.planId + " · #" + recordsPopup.current.waypoint : "--"; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 10 }
                            }
                            Column { spacing: 3
                                Text { text: "기록 유발"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 8 }
                                Text { text: recordsPopup.current ? recordsPopup.current.trigger : "--"; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 10 }
                            }
                        }
                        Row {
                            spacing: 24; visible: recordsPopup.expanded && recordsPopup.current && recordsPopup.current.reasons !== ""
                            Column { spacing: 3
                                Text { text: "안전 사유"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 8 }
                                Text { text: recordsPopup.current ? recordsPopup.current.reasons : "--"; color: amber; font.family: "Noto Sans CJK KR"; font.pixelSize: 9 }
                            }
                        }
                    }
                }
            }
        }
    }

    Popup {
        id: missionPopup
        modal: true; focus: true
        x: (Overlay.overlay.width - width) / 2; y: 2
        width: 780; height: 440; padding: 0
        onOpened: dashboard.setOnScreenKeyboardVisible(false)
        property bool executing: dashboard.planReady
        property bool paused: dashboard.missionState === "PAUSED_USER" || dashboard.missionState === "PAUSED_SAFETY"
        property int completed: dashboard.currentWaypoint
        property int waypointCount: dashboard.totalWaypoints
        property string planId: dashboard.planId
        property var planValues: ["12.0", "8.0", "0.40", "20", "0.20", "좌상단"]
        // QML은 배열 원소만 바꾸는 걸(planValues[i] = x) 변경으로 감지 못해 바인딩이 안 갱신된다.
        // 항상 배열을 통째로 새로 만들어 대입해야 화면(선택 강조 등)이 즉시 반영된다.
        function setPlanValue(i, v) { var arr = planValues.slice(); arr[i] = v; planValues = arr }
        background: Rectangle { color: "#24231F"; border.color: line; border.width: 1 }
        contentItem: Item {
            anchors.fill: parent
            MouseArea { anchors.fill: parent; onClicked: { missionPopup.forceActiveFocus(); dashboard.setOnScreenKeyboardVisible(false) } }
            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 48; color: raised
                Text { anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter; text: missionPopup.executing ? "반자율 전면점검 · 실행" : "반자율 전면점검 · 계획"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 16; font.bold: true }
                Text { anchors.right: parent.right; anchors.rightMargin: 15; anchors.verticalCenter: parent.verticalCenter; text: "×"; color: ink; font.pixelSize: 24; TapHandler { onTapped: missionPopup.close() } }
            }
            Item {
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.margins: 16; anchors.topMargin: 60
                visible: !missionPopup.executing
                Grid { columns: 2; columnSpacing: 12; rowSpacing: 6; anchors.left: parent.left; anchors.top: parent.top
                    Repeater { model: ["사일로 폭 (m)", "사일로 높이 (m)", "점검폭 (m)", "중첩률 (%)", "안전여백 (m)"]
                        delegate: Column { required property var modelData; required property int index; width: 220; spacing: 4
                            Text { text: modelData; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 10 }
                            TextField { width: 220; height: 31; text: missionPopup.planValues[index]; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 12; onEditingFinished: missionPopup.setPlanValue(index, text); onActiveFocusChanged: dashboard.setOnScreenKeyboardVisible(activeFocus); background: Rectangle { color: "#171716"; border.color: line; border.width: 1 } }
                        }
                    }
                }
                // 사일로는 세로로 긴 원통이라, 벽면을 펼친 전개도도 가로가 아니라 세로로 길게 그린다.
                // 시작 모서리 4곳을 후보로 미리 그려서 눌러 고르게 한다(직접 값을 타이핑하지 않음).
                Rectangle { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 210; color: "#191917"; border.color: line; border.width: 1
                    Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.top: parent.top; anchors.topMargin: 10; text: "시작 모서리 후보 선택"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true }
                    Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.top: parent.top; anchors.topMargin: 27; text: "탭해서 선택 · 현재: " + missionPopup.planValues[5]; color: amber; font.family: "Noto Sans CJK KR"; font.pixelSize: 8; font.bold: true }
                    Grid {
                        anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: 46
                        columns: 2; columnSpacing: 6; rowSpacing: 6
                        Repeater {
                            model: ["좌상단", "우상단", "좌하단", "우하단"]
                            delegate: Rectangle {
                                id: candidateTile
                                required property string modelData
                                readonly property bool selected: missionPopup.planValues[5] === modelData
                                readonly property bool startLeft: modelData.charAt(0) === "좌"
                                readonly property bool startTop: modelData.indexOf("상") >= 0
                                width: 95; height: 150
                                color: "#131211"; border.color: selected ? amber : "#59544B"; border.width: selected ? 2 : 1
                                Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: 4; text: candidateTile.modelData; color: candidateTile.selected ? amber : muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 9; font.bold: true }
                                Item {
                                    id: track
                                    anchors.left: parent.left; anchors.leftMargin: 12; anchors.right: parent.right; anchors.rightMargin: 12
                                    anchors.top: parent.top; anchors.topMargin: 22; anchors.bottom: parent.bottom; anchors.bottomMargin: 8
                                    readonly property int rows: 5
                                    readonly property real rowSpacing: rows > 1 ? (height - 12) / (rows - 1) : 0
                                    function rowY(i) { return candidateTile.startTop ? 6 + i * track.rowSpacing : track.height - 6 - i * track.rowSpacing }
                                    Repeater {
                                        model: track.rows
                                        delegate: Rectangle { x: 0; width: track.width; height: 2; y: track.rowY(index); color: index === 0 ? amber : "#8A8478" }
                                    }
                                    Repeater {
                                        model: track.rows - 1
                                        delegate: Rectangle {
                                            required property int index
                                            readonly property bool isRight: (index % 2 === 0) === candidateTile.startLeft
                                            x: isRight ? track.width - 2 : 0; width: 2
                                            y: Math.min(track.rowY(index), track.rowY(index + 1))
                                            height: Math.abs(track.rowY(index + 1) - track.rowY(index))
                                            color: "#8A8478"
                                        }
                                    }
                                    Rectangle { x: candidateTile.startLeft ? -3 : track.width - 5; y: track.rowY(0) - 4; width: 8; height: 8; radius: 4; color: amber; border.color: "#F2DDA8"; border.width: 1 }
                                }
                                TapHandler { onTapped: missionPopup.setPlanValue(5, candidateTile.modelData) }
                            }
                        }
                    }
                }
                Rectangle {
                    anchors.right: parent.right; anchors.rightMargin: 220; anchors.bottom: parent.bottom
                    width: 140; height: 34; color: "#C3A36A"; border.color: "#E9D4A4"; border.width: 1
                    Text { anchors.centerIn: parent; text: "추천 경로 생성"; color: "#211D18"; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true }
                    TapHandler {
                        onTapped: {
                            var corners = {"좌하단":"BOTTOM_LEFT", "우하단":"BOTTOM_RIGHT", "좌상단":"TOP_LEFT", "우상단":"TOP_RIGHT"}
                            dashboard.requestRoutePlan(Number(missionPopup.planValues[0]), Number(missionPopup.planValues[1]), Number(missionPopup.planValues[2]), Number(missionPopup.planValues[3]) / 100.0, Number(missionPopup.planValues[4]), corners[missionPopup.planValues[5]] || "TOP_LEFT")
                        }
                    }
                }

                // 실제 계산 결과(세로/가로 후보 비교)를 흩어진 텍스트 줄이 아니라 나란히 놓은
                // 카드 두 개로 보여준다 — 채택된 쪽이 한눈에 강조되게.
                Row {
                    anchors.left: parent.left; anchors.top: parent.top; anchors.topMargin: 175
                    spacing: 10
                    visible: dashboard.planReady
                    Repeater {
                        model: dashboard.planCandidates
                        delegate: Rectangle {
                            required property var modelData
                            readonly property bool adopted: modelData.orientation === dashboard.planOrientation
                            width: 205; height: 74
                            color: adopted ? "#2E2A20" : "#191917"; border.color: adopted ? amber : "#4A463D"; border.width: adopted ? 2 : 1
                            Row {
                                anchors.left: parent.left; anchors.leftMargin: 10; anchors.top: parent.top; anchors.topMargin: 8; spacing: 6
                                Rectangle { width: 8; height: 8; radius: 4; anchors.verticalCenter: parent.verticalCenter; color: adopted ? amber : "#59544B" }
                                Text { text: (modelData.orientation === "VERTICAL" ? "세로 지그재그" : "가로 지그재그") + (adopted ? " · 채택" : ""); color: adopted ? amber : muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 10; font.bold: true }
                            }
                            Text { anchors.left: parent.left; anchors.leftMargin: 10; anchors.top: parent.top; anchors.topMargin: 30; text: "거리 " + Number(modelData.estimated_length_m).toFixed(2) + " m"; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 11 }
                            Text { anchors.left: parent.left; anchors.leftMargin: 10; anchors.top: parent.top; anchors.topMargin: 50; text: "회전 " + modelData.turn_count + "회"; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 11 }
                        }
                    }
                }
                Text {
                    visible: dashboard.planReady
                    anchors.left: parent.left; anchors.top: parent.top; anchors.topMargin: 254
                    text: "웨이포인트 " + dashboard.planWaypoints.length + "개 생성됨 — \"실행\" 탭에서 경로 확인"
                    color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 9
                }
            }
            Item {
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.margins: 16; anchors.topMargin: 60
                visible: missionPopup.executing
                Rectangle { id: execPanel; anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 400; color: "#171716"; border.color: line; border.width: 1
                    Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.top: parent.top; anchors.topMargin: 10; text: "사일로 전개도"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 12; font.bold: true }
                    Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.top: parent.top; anchors.topMargin: 27; text: missionPopup.planId; color: muted; font.family: "DejaVu Sans Mono"; font.pixelSize: 8 }
                    Rectangle {
                        id: execSilo
                        anchors.left: parent.left; anchors.leftMargin: 40; anchors.right: parent.right; anchors.rightMargin: 40
                        anchors.top: parent.top; anchors.topMargin: 48; anchors.bottom: parent.bottom; anchors.bottomMargin: 16
                        color: "transparent"; border.color: "#6B665C"; border.width: 1
                        // 웨이포인트 실좌표(폭·높이 축척 그대로)를 직접 그린다 — 줄 수를 임의로
                        // 24개로 잘라 보여주면 입력값이 달라져도(37개든 74개든) 화면이 똑같아
                        // 보이는 문제가 있었다. 이제는 개수와 무관하게 실제 경로 모양이 그대로 나온다.
                        readonly property real scaleW: Math.max(0.001, dashboard.planWidth)
                        readonly property real scaleH: Math.max(0.001, dashboard.planHeight)
                        function toPoint(wp) {
                            return Qt.point((wp.x / execSilo.scaleW) * execSilo.width,
                                            execSilo.height - (wp.y / execSilo.scaleH) * execSilo.height)
                        }
                        readonly property var allPoints: {
                            var pts = []
                            var wps = dashboard.planWaypoints
                            for (var i = 0; i < wps.length; i++) pts.push(execSilo.toPoint(wps[i]))
                            return pts
                        }
                        readonly property var completedPoints:
                            execSilo.allPoints.slice(0, Math.min(execSilo.allPoints.length, missionPopup.completed + 1))
                        // 1m 간격 배경 격자 + 높이 눈금 — 맨선만 있을 때보다 "실측 도면"처럼 보이게 하고,
                        // 실제 사일로 높이 감을 잡을 수 있게 한다.
                        readonly property int gridLines: Math.max(1, Math.round(execSilo.scaleH))
                        Repeater {
                            model: execSilo.gridLines + 1
                            delegate: Item {
                                required property int index
                                readonly property real gy: execSilo.height - (index / execSilo.gridLines) * execSilo.height
                                Rectangle { x: 0; y: parent.gy; width: execSilo.width; height: 1; color: "#2C2A25" }
                                Text {
                                    x: -32; y: parent.gy - 5; width: 28
                                    horizontalAlignment: Text.AlignRight
                                    text: (index * execSilo.scaleH / execSilo.gridLines).toFixed(execSilo.scaleH < 1 ? 1 : 0) + "m"
                                    color: "#5C584F"; font.family: "DejaVu Sans Mono"; font.pixelSize: 7
                                }
                            }
                        }
                        Shape {
                            anchors.fill: parent
                            ShapePath {
                                strokeColor: "#5E5A50"; strokeWidth: 3; fillColor: "transparent"
                                capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
                                PathPolyline { path: execSilo.allPoints }
                            }
                            ShapePath {
                                strokeColor: safe; strokeWidth: 3; fillColor: "transparent"
                                capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
                                PathPolyline { path: execSilo.completedPoints.length > 1 ? execSilo.completedPoints : [] }
                            }
                        }
                        // 선만 있으면 추상적으로 보여서, 경유점마다 작은 점을 찍어 "정차 지점이
                        // 있는 실제 경로"처럼 보이게 한다.
                        Repeater {
                            model: execSilo.allPoints
                            delegate: Rectangle {
                                required property var modelData
                                required property int index
                                width: 5; height: 5; radius: 2.5
                                color: index < execSilo.completedPoints.length ? safe : "#6B665C"
                                x: modelData.x - 2.5; y: modelData.y - 2.5
                            }
                        }
                        Rectangle {
                            visible: execSilo.allPoints.length > 0
                            x: (execSilo.allPoints.length > 0 ? execSilo.allPoints[0].x : 0) - 4
                            y: (execSilo.allPoints.length > 0 ? execSilo.allPoints[0].y : 0) - 4
                            width: 8; height: 8; radius: 4; color: amber
                        }
                        // 실시간 위치 마커 — 웨이포인트 "도착" 여부와 무관하게 나노가 계산한
                        // 현재 pose(x,y)를 그대로 찍는다. 예전엔 도착 전엔 아예 안 움직여서
                        // "진행이 되고 있는지 아닌지" 화면만으로는 알 수 없었다.
                        readonly property point livePoint: dashboard.poseValid
                            ? execSilo.toPoint({x: dashboard.poseX, y: dashboard.poseY})
                            : (execSilo.allPoints.length > 0 ? execSilo.allPoints[0] : Qt.point(0, 0))
                        Shape {
                            anchors.fill: parent
                            visible: dashboard.poseValid
                            ShapePath {
                                strokeColor: "#DCC69A"; strokeWidth: 2; fillColor: "transparent"
                                capStyle: ShapePath.RoundCap
                                // 화면 y축은 위로 갈수록 값이 커지게 뒤집어 그리므로(toPoint 참조),
                                // 방향 표시도 같은 부호로 뒤집어야 실제 진행 방향과 일치한다.
                                PathPolyline { path: [
                                    execSilo.livePoint,
                                    Qt.point(execSilo.livePoint.x + 16 * Math.cos(dashboard.poseTheta),
                                             execSilo.livePoint.y - 16 * Math.sin(dashboard.poseTheta))
                                ] }
                            }
                        }
                        Item {
                            visible: execSilo.allPoints.length > 0
                            x: execSilo.livePoint.x; y: execSilo.livePoint.y
                            Rectangle { anchors.centerIn: parent; width: 18; height: 18; radius: 9; color: "#3A2E13"; border.color: "#DCC69A"; border.width: 1; opacity: 0.6 }
                            Rectangle { anchors.centerIn: parent; width: 10; height: 10; radius: 5; color: "#DCC69A"; border.color: "#241E17"; border.width: 1 }
                        }
                    }
                    Text {
                        visible: dashboard.planReady
                        anchors.left: parent.left; anchors.leftMargin: 12; anchors.bottom: parent.bottom; anchors.bottomMargin: 4
                        text: dashboard.planEstimatedLength.toFixed(1) + " m · 회전 " + dashboard.planTurnCount + "회"
                        color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 7
                    }
                }
                Column { anchors.left: execPanel.right; anchors.leftMargin: 16; anchors.right: parent.right; anchors.top: parent.top; spacing: 10
                    Text { text: "진행률  " + Math.round(100 * missionPopup.completed / Math.max(1, missionPopup.waypointCount)) + "%"; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 26; font.bold: true }
                    Text { text: "WAYPOINT  " + missionPopup.completed + " / " + missionPopup.waypointCount; color: muted; font.family: "DejaVu Sans Mono"; font.pixelSize: 11 }
                    Text { text: dashboard.safetyState === "NORMAL" ? "안전 상태 정상" : "안전 이벤트: " + dashboard.safetyReasons.join(" · "); color: window.safetyColor(dashboard.safetyState); width: parent.width; wrapMode: Text.WordWrap; font.family: "Noto Sans CJK KR"; font.pixelSize: 10; font.bold: true }
                    Grid {
                        columns: 2; columnSpacing: 6; rowSpacing: 6
                        Repeater {
                            model: [
                                {label: "시작/재개", action: "startpause"},
                                {label: "취소", action: "route_cancel"},
                                {label: "비상정지", action: "estop"},
                                {label: "해제 요청", action: "release"}
                            ]
                            delegate: Rectangle {
                                id: missionBtn
                                required property var modelData
                                width: 150; height: 32
                                color: modelData.action === "estop" ? "#4A2E2E" : "#3D3933"
                                border.color: modelData.action === "estop" ? "#8A5A5A" : "#777065"; border.width: 1
                                Text {
                                    anchors.centerIn: parent
                                    text: missionBtn.modelData.action === "startpause"
                                        ? (dashboard.missionState === "READY" ? "시작" : (missionPopup.paused ? "재개" : "일시정지"))
                                        : missionBtn.modelData.label
                                    color: missionBtn.modelData.action === "estop" ? "#F0D8D8" : ink
                                    font.family: "Noto Sans CJK KR"; font.pixelSize: 10; font.bold: true
                                }
                                TapHandler {
                                    onTapped: {
                                        switch (missionBtn.modelData.action) {
                                        case "startpause": dashboard.sendAutonomyCommand(dashboard.missionState === "READY" ? "route_start" : (missionPopup.paused ? "route_resume" : "route_pause")); break
                                        case "route_cancel": dashboard.sendAutonomyCommand("route_cancel"); break
                                        case "estop": dashboard.emergencyStop(); break
                                        case "release": dashboard.releaseEmergencyStop(); break
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Text { text: dashboard.releaseFeedback; color: danger; width: parent.width; wrapMode: Text.WordWrap; font.family: "Noto Sans CJK KR"; font.pixelSize: 9 }
                }
            }
        }
    }

    Popup {
        id: connectionPopup
        modal: true; focus: true
        x: (Overlay.overlay.width - width) / 2; y: 2
        width: 796; height: 300; padding: 0
        onOpened: { dashboardHostField.text = dashboard.advertisedHost; rtspField.text = dashboard.rtspUrl; websocketPortField.text = dashboard.websocketPort; connectionFeedback.text = "저장된 연결 정보를 불러왔습니다."; connectionFeedback.color = muted }
        background: Rectangle { color: "#2A2825"; border.color: "#777066"; border.width: 1 }
        contentItem: Item {
            anchors.fill: parent
            MouseArea { anchors.fill: parent; onClicked: { connectionPopup.forceActiveFocus(); dashboard.setOnScreenKeyboardVisible(false) } }
            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 52; color: "#36332E"; border.color: line; border.width: 1 }
            Text { anchors.left: parent.left; anchors.leftMargin: 18; anchors.top: parent.top; anchors.topMargin: 12; text: "연결 설정"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 17; font.bold: true }
            Text { anchors.left: parent.left; anchors.leftMargin: 18; anchors.top: parent.top; anchors.topMargin: 34; text: "CONNECTION CONFIGURATION"; color: muted; font.family: "DejaVu Sans Mono"; font.pixelSize: 8; font.bold: true; font.letterSpacing: 1.1 }
            Text { anchors.right: parent.right; anchors.rightMargin: 16; anchors.top: parent.top; anchors.topMargin: 8; text: "×"; color: "#E4DED3"; font.pixelSize: 27; TapHandler { onTapped: connectionPopup.close() } }
            Rectangle {
                anchors.right: parent.right; anchors.rightMargin: 52; anchors.top: parent.top; anchors.topMargin: 11
                width: 96; height: 30; color: raised; border.color: line; border.width: 1
                Text { anchors.centerIn: parent; text: "키보드 숨기기"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 10; font.bold: true }
                TapHandler {
                    onTapped: {
                        dashboardHostField.focus = false
                        rtspField.focus = false
                        websocketPortField.focus = false
                        dashboard.setOnScreenKeyboardVisible(false)
                    }
                }
            }
            Column {
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.leftMargin: 8; anchors.rightMargin: 8; anchors.topMargin: 60; spacing: 7
                Column { width: parent.width; spacing: 4; Text { text: "대시보드 Tailscale 주소"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true } TextField { id: dashboardHostField; width: parent.width; height: 31; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 12; placeholderText: "예: 100.74.141.112"; placeholderTextColor: muted; selectByMouse: true; onActiveFocusChanged: dashboard.setOnScreenKeyboardVisible(activeFocus); background: Rectangle { color: "#1B1A18"; border.color: dashboardHostField.activeFocus ? "#C3A36A" : line; border.width: 1 } } }
                Column { width: parent.width; spacing: 4; Text { text: "카메라 RTSP 주소"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true } TextField { id: rtspField; width: parent.width; height: 31; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 12; placeholderText: "rtsp://<nano-ip>:8554/robot"; placeholderTextColor: muted; selectByMouse: true; onActiveFocusChanged: dashboard.setOnScreenKeyboardVisible(activeFocus); background: Rectangle { color: "#1B1A18"; border.color: rtspField.activeFocus ? "#C3A36A" : line; border.width: 1 } } }
                Row { spacing: 16; Column { spacing: 4; Text { text: "WebSocket 포트"; color: ink; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true } TextField { id: websocketPortField; width: 180; height: 31; color: ink; font.family: "DejaVu Sans Mono"; font.pixelSize: 12; inputMethodHints: Qt.ImhDigitsOnly; selectByMouse: true; onActiveFocusChanged: dashboard.setOnScreenKeyboardVisible(activeFocus); background: Rectangle { color: "#1B1A18"; border.color: websocketPortField.activeFocus ? "#C3A36A" : line; border.width: 1 } } } Column { spacing: 5; Text { text: "Nano / Orin 접속점"; color: muted; font.family: "Noto Sans CJK KR"; font.pixelSize: 10; font.bold: true } Text { text: dashboard.dashboardEndpoint; color: "#DCC69A"; font.family: "DejaVu Sans Mono"; font.pixelSize: 11; font.bold: true } } }
                Text { id: connectionFeedback; font.family: "Noto Sans CJK KR"; font.pixelSize: 10 }
            }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 18; anchors.bottom: parent.bottom; anchors.bottomMargin: 18; spacing: 8
                Rectangle { width: 110; height: 34; color: "#413D37"; border.color: line; border.width: 1
                    Text { anchors.centerIn: parent; text: "취소"; color: "#E3DDD2"; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true }
                    TapHandler { onTapped: connectionPopup.close() }
                }
                Rectangle { width: 150; height: 34; color: "#C3A36A"; border.color: "#E9D4A4"; border.width: 1
                    Text { anchors.centerIn: parent; text: "저장 및 적용"; color: "#211D18"; font.family: "Noto Sans CJK KR"; font.pixelSize: 11; font.bold: true }
                    TapHandler {
                        onTapped: {
                            const port = Number(websocketPortField.text)
                            const saved = dashboard.saveConnectionSettings(dashboardHostField.text, rtspField.text, port)
                            if (saved) {
                                connectionFeedback.text = "저장했습니다. 새 연결 설정을 적용합니다."
                                connectionFeedback.color = safe
                            } else {
                                connectionFeedback.text = "저장하지 못했습니다. 주소와 포트를 확인하세요."
                                connectionFeedback.color = "#E69A9B"
                            }
                            // rtspUrl 값이 그대로여도(같은 주소 재저장) 재생을 강제로 다시 건다 —
                            // 백엔드는 값이 안 바뀌면 신호를 안 보내 MediaPlayer가 재시도를 안 한다.
                            player.stop()
                            player.play()
                        }
                    }
                }
            }
        }
    }
}
