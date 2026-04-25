import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  SessionTimerWidget -- session elapsed time + type badge (200 x 80).
    Hero elapsed time display with session type badge, remaining
    time that flashes when low, and optional thin progress bar.      */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 200
    height: 80
    color: "transparent"

    // -- public API -------------------------------------------------------
    property string elapsed: "0:00:00"
    property string sessionType: "Practice"
    property string timeRemaining: ""
    // T168: degraded state — session telemetry stalled. When
    // true the hero elapsed readout flips to "—:——:——" in
    // steel, distinguishing "no data" from "session paused at
    // 0:00:00".
    property bool degraded: false

    // -- derived ----------------------------------------------------------
    readonly property string _safeType: (typeof sessionType === "string" && sessionType.length > 0)
                                        ? sessionType : "Practice"

    readonly property color sessionColor: {
        var lower = _safeType.toLowerCase()
        if (lower === "qualifying" || lower === "quali")
            return Theme.Tokens.racingPurple
        if (lower === "race")
            return Theme.Tokens.safetyRed
        if (lower === "warmup" || lower === "warm up")
            return Theme.Tokens.marshalYellow
        return Theme.Tokens.acidGreen   // practice / other
    }

    readonly property bool hasRemaining: typeof timeRemaining === "string"
                                         && timeRemaining.length > 0

    // Estimate if remaining time is < 5 min for flash.
    // Parses "M:SS" or "H:MM:SS" patterns.
    readonly property bool lowTime: {
        if (!hasRemaining) return false
        var parts = timeRemaining.split(":")
        if (parts.length === 2) {
            // M:SS
            var min = parseInt(parts[0], 10)
            return !isNaN(min) && min < 5
        }
        if (parts.length === 3) {
            // H:MM:SS
            var hrs = parseInt(parts[0], 10)
            var mins = parseInt(parts[1], 10)
            return !isNaN(hrs) && !isNaN(mins) && hrs === 0 && mins < 5
        }
        return false
    }

    // Progress ratio (0-1) based on elapsed vs total
    readonly property real progressRatio: {
        if (!hasRemaining) return -1  // no progress bar
        function parseSecs(str) {
            var p = str.split(":")
            if (p.length === 2) return parseInt(p[0],10)*60 + parseInt(p[1],10)
            if (p.length === 3) return parseInt(p[0],10)*3600 + parseInt(p[1],10)*60 + parseInt(p[2],10)
            return 0
        }
        var elapsedS = parseSecs(elapsed)
        var remainS = parseSecs(timeRemaining)
        var total = elapsedS + remainS
        if (total <= 0) return -1
        return Math.max(0, Math.min(1, elapsedS / total))
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 8
            bottomMargin: 8
            leftMargin: 14
            rightMargin: 14
        }
        spacing: 0

        // -- Row 1: Session type badge ------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Rectangle {
                implicitWidth: typeBadgeText.implicitWidth + 12
                implicitHeight: 16
                radius: 4
                color: Theme.Tokens.subtle(root.sessionColor, 0.12)
                border.width: 1
                border.color: Theme.Tokens.subtle(root.sessionColor, 0.25)

                Behavior on color { ColorAnimation { duration: 300 } }
                Behavior on border.color { ColorAnimation { duration: 300 } }

                Text {
                    id: typeBadgeText
                    anchors.centerIn: parent
                    text: root._safeType.toUpperCase()
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(8 * root.fontScale)
                    font.weight: Font.Bold
                    font.letterSpacing: 1.0
                    color: root.sessionColor

                    Behavior on color { ColorAnimation { duration: 300 } }
                }
            }

            Item { Layout.fillWidth: true }

            // Remaining label (small, top-right)
            Text {
                visible: root.hasRemaining
                text: root.timeRemaining + " rem"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(9 * root.fontScale)
                font.weight: Font.DemiBold
                color: root.lowTime ? Theme.Tokens.safetyRed : Theme.Tokens.steel
                opacity: _flashAnim.running ? _flashAnim._opacity : 1.0

                Behavior on color { ColorAnimation { duration: 200 } }
            }
        }

        // -- Row 2: Elapsed time (hero) -----------------------------------
        Text {
            text: root.degraded ? "—:——:——" : root.elapsed
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(26 * root.fontScale)
            font.weight: Font.Bold
            color: root.degraded ? Theme.Tokens.steel : Theme.Tokens.chalk
            Layout.topMargin: 4
        }

        // -- Row 3: Remaining time (flashes when low) ---------------------
        Text {
            visible: root.hasRemaining
            text: root.timeRemaining + " remaining"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(10 * root.fontScale)
            font.weight: Font.DemiBold
            color: root.lowTime ? Theme.Tokens.safetyRed : Theme.Tokens.steel
            opacity: root.lowTime
                     ? _flashAnim._opacity
                     : 1.0
            Layout.topMargin: 2

            Behavior on color { ColorAnimation { duration: 200 } }
        }

        Item { Layout.preferredHeight: 4 }

        // -- Row 4: Thin progress bar -------------------------------------
        Item {
            visible: root.progressRatio >= 0
            Layout.fillWidth: true
            Layout.preferredHeight: 3

            Rectangle {
                anchors.fill: parent
                radius: 1.5
                color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.06)
            }

            Rectangle {
                anchors {
                    left: parent.left
                    top: parent.top
                    bottom: parent.bottom
                }
                width: Math.max(0, parent.width * root.progressRatio)
                radius: 1.5
                color: root.sessionColor
                opacity: 0.5

                Behavior on width { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
                Behavior on color { ColorAnimation { duration: 300 } }
            }
        }
    }

    // -- Flash animation for low time -------------------------------------
    Timer {
        id: _flashAnim
        property real _opacity: 1.0
        interval: 500
        repeat: true
        running: root.lowTime
        onTriggered: _opacity = (_opacity < 0.9) ? 1.0 : 0.3
        onRunningChanged: if (!running) _opacity = 1.0
    }
}
