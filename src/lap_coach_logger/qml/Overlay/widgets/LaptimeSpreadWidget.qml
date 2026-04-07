import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  LaptimeSpreadWidget — horizontal range bar (300 x 160).
    Shows spread between fastest and slowest lap times with
    markers for current and average.                             */
Rectangle {
    id: root
    width: 300
    height: 160
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real fastestTime: 0.0
    property real slowestTime: 0.0
    property real currentTime: 0.0
    property real averageTime: 0.0

    readonly property real spread: slowestTime - fastestTime

    function formatTime(s) {
        if (s <= 0) return "-:---.---"
        var mins = Math.floor(s / 60)
        var secs = s - mins * 60
        return mins + ":" + (secs < 10 ? "0" : "") + secs.toFixed(3)
    }

    function positionPct(t) {
        if (spread < 0.001) return 0.5
        return Math.max(0, Math.min(1, (t - fastestTime) / spread))
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 14
            rightMargin: 14
        }
        spacing: 6

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "LAP TIME SPREAD"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root.spread > 0
                      ? root.spread.toFixed(3) + "s"
                      : "--"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 11
                font.weight: Font.Bold
                color: Theme.Tokens.pitOrange
            }
        }

        // ── Range bar ──────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 40

            // Track
            Rectangle {
                id: track
                anchors {
                    left: parent.left
                    right: parent.right
                    verticalCenter: parent.verticalCenter
                }
                height: 6
                radius: 3
                color: Qt.rgba(Theme.Tokens.chalk.r,
                               Theme.Tokens.chalk.g,
                               Theme.Tokens.chalk.b, 0.06)

                // Filled range
                Rectangle {
                    anchors {
                        left: parent.left
                        top: parent.top
                        bottom: parent.bottom
                    }
                    width: parent.width
                    radius: 3
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: Theme.Tokens.acidGreen }
                        GradientStop { position: 0.5; color: Theme.Tokens.pitOrange }
                        GradientStop { position: 1.0; color: Theme.Tokens.safetyRed }
                    }
                    opacity: 0.4
                }
            }

            // Average marker (line)
            Rectangle {
                visible: root.averageTime > 0
                x: track.x + track.width * root.positionPct(root.averageTime) - 0.5
                anchors.verticalCenter: parent.verticalCenter
                width: 1
                height: 20
                color: Theme.Tokens.marshalYellow
                opacity: 0.6

                Behavior on x { NumberAnimation { duration: 200 } }
            }

            // Current time marker (dot)
            Rectangle {
                visible: root.currentTime > 0
                x: track.x + track.width * root.positionPct(root.currentTime) - 5
                anchors.verticalCenter: parent.verticalCenter
                width: 10
                height: 10
                radius: 5
                color: Theme.Tokens.chalk
                border.width: 2
                border.color: Theme.Tokens.racingPurple

                Behavior on x { NumberAnimation { duration: 200 } }
            }
        }

        // ── Divider ────────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 6
            Rectangle {
                anchors.centerIn: parent
                width: parent.width
                height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5; color: Qt.rgba(Theme.Tokens.chalk.r,
                                                                  Theme.Tokens.chalk.g,
                                                                  Theme.Tokens.chalk.b, 0.08) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // ── Data rows ──────────────────────────────────────────────
        GridLayout {
            Layout.fillWidth: true
            columns: 2
            rowSpacing: 4
            columnSpacing: 12

            Text {
                text: "FASTEST"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.0
                color: Theme.Tokens.steel
            }
            Text {
                text: root.formatTime(root.fastestTime)
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 13
                font.weight: Font.Bold
                color: Theme.Tokens.acidGreen
                Layout.alignment: Qt.AlignRight
            }

            Text {
                text: "SLOWEST"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.0
                color: Theme.Tokens.steel
            }
            Text {
                text: root.formatTime(root.slowestTime)
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 13
                font.weight: Font.Bold
                color: Theme.Tokens.safetyRed
                Layout.alignment: Qt.AlignRight
            }

            Text {
                text: "AVERAGE"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.0
                color: Theme.Tokens.steel
            }
            Text {
                text: root.formatTime(root.averageTime)
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 13
                font.weight: Font.Bold
                color: Theme.Tokens.marshalYellow
                Layout.alignment: Qt.AlignRight
            }
        }
    }
}
