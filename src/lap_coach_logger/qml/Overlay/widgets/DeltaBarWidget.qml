import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  DeltaBarWidget — horizontal delta bar (300 x 60).
    Green left (faster), red right (slower). Delta number
    centered over the bar.                                       */
Rectangle {
    id: root
    width: 300
    height: 60
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real delta: 0.0
    property real maxDelta: 2.0

    function formatDelta(d) {
        if (d === 0) return "+0.000"
        var sign = d > 0 ? "+" : ""
        return sign + d.toFixed(3)
    }

    readonly property color deltaColor: {
        if (delta < 0) return Theme.Tokens.acidGreen
        if (delta > 0) return Theme.Tokens.safetyRed
        return Theme.Tokens.steel
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 8
            bottomMargin: 8
            leftMargin: 14
            rightMargin: 14
        }
        spacing: 4

        // ── Delta number ───────────────────────────────────────────
        Text {
            text: root.formatDelta(root.delta)
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 18
            font.weight: Font.Bold
            color: root.deltaColor
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true

            Behavior on color { ColorAnimation { duration: 200 } }
        }

        // ── Bar ────────────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 16

            // Track background
            Rectangle {
                id: barTrack
                anchors.fill: parent
                radius: 4
                color: Qt.rgba(Theme.Tokens.chalk.r,
                               Theme.Tokens.chalk.g,
                               Theme.Tokens.chalk.b, 0.06)
            }

            // Center line
            Rectangle {
                anchors {
                    horizontalCenter: parent.horizontalCenter
                    top: parent.top
                    bottom: parent.bottom
                }
                width: 2
                color: Qt.rgba(Theme.Tokens.chalk.r,
                               Theme.Tokens.chalk.g,
                               Theme.Tokens.chalk.b, 0.20)
                z: 2
            }

            // Delta fill
            Rectangle {
                id: deltaFill
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height
                radius: 4

                readonly property real pct: Math.max(0, Math.min(1,
                    Math.abs(root.delta) / root.maxDelta))

                // Negative delta (faster): grows left from center
                // Positive delta (slower): grows right from center
                x: root.delta <= 0
                   ? parent.width / 2 - width
                   : parent.width / 2

                width: parent.width / 2 * pct

                color: Qt.rgba(root.deltaColor.r,
                               root.deltaColor.g,
                               root.deltaColor.b, 0.6)

                Behavior on width { NumberAnimation { duration: 80 } }
                Behavior on x { NumberAnimation { duration: 80 } }
                Behavior on color { ColorAnimation { duration: 200 } }
            }
        }

        // ── Labels ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true

            Text {
                text: "FASTER"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 1.0
                color: Theme.Tokens.acidGreen
                opacity: 0.6
            }

            Item { Layout.fillWidth: true }

            Text {
                text: "SLOWER"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 1.0
                color: Theme.Tokens.safetyRed
                opacity: 0.6
            }
        }
    }
}
