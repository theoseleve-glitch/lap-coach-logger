import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  SessionTimerWidget — session elapsed time + type badge (200 x 80).
    Simple session timer with session type indicator and
    optional remaining time display.                               */
Rectangle {
    id: root
    width: 200
    height: 80
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property string elapsed: "0:00:00"
    property string sessionType: "Practice"
    property string timeRemaining: ""

    // ── session type color ──────────────────────────────────────────
    readonly property color sessionColor: {
        var lower = sessionType.toLowerCase()
        if (lower === "qualifying" || lower === "quali")
            return Theme.Tokens.racingPurple
        if (lower === "race")
            return Theme.Tokens.safetyRed
        return Theme.Tokens.acidGreen   // practice / other
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 14
            rightMargin: 14
        }
        spacing: 0

        // ── Row 1: Session type badge ──────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Rectangle {
                implicitWidth: typeBadgeText.implicitWidth + 10
                implicitHeight: 16
                radius: 4
                color: Qt.rgba(root.sessionColor.r,
                               root.sessionColor.g,
                               root.sessionColor.b, 0.12)
                border.width: 1
                border.color: Qt.rgba(root.sessionColor.r,
                                      root.sessionColor.g,
                                      root.sessionColor.b, 0.25)

                Text {
                    id: typeBadgeText
                    anchors.centerIn: parent
                    text: root.sessionType.toUpperCase()
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.Bold
                    font.letterSpacing: 1.0
                    color: root.sessionColor
                }
            }

            Item { Layout.fillWidth: true }
        }

        // ── Row 2: Elapsed time (hero) ─────────────────────────────
        Text {
            text: root.elapsed
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 24
            font.weight: Font.Bold
            color: Theme.Tokens.chalk
            Layout.topMargin: 4
        }

        // ── Row 3: Remaining (if available) ────────────────────────
        Text {
            visible: root.timeRemaining.length > 0
            text: root.timeRemaining + " remaining"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 10
            font.weight: Font.DemiBold
            color: Theme.Tokens.steel
            Layout.topMargin: 2
        }
    }
}
