import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  RadarBarsWidget — horizontal proximity bars (200 x 120).
    Left bar fills from right, right bar fills from left.
    Color shifts to red when danger flag is set.                */
Rectangle {
    id: root
    width: 200
    height: 120
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real leftProximity: 0.0   // 0-1
    property real rightProximity: 0.0  // 0-1
    property bool leftDanger: false
    property bool rightDanger: false

    readonly property color leftColor: leftDanger
        ? Theme.Tokens.safetyRed : Theme.Tokens.pitOrange
    readonly property color rightColor: rightDanger
        ? Theme.Tokens.safetyRed : Theme.Tokens.pitOrange

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 12
            rightMargin: 12
        }
        spacing: 6

        // ── Header ─────────────────────────────────────────────────
        Text {
            text: "PROXIMITY"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 9
            font.weight: Font.Bold
            font.letterSpacing: 1.2
            color: Theme.Tokens.steel
        }

        // ── Left bar ──────────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Text {
                text: "LEFT"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 1.0
                color: Theme.Tokens.steel
                opacity: 0.7
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 20

                // Track
                Rectangle {
                    anchors.fill: parent
                    radius: 4
                    color: Qt.rgba(Theme.Tokens.chalk.r,
                                   Theme.Tokens.chalk.g,
                                   Theme.Tokens.chalk.b, 0.06)
                }

                // Fill (right-to-left)
                Rectangle {
                    anchors {
                        top: parent.top
                        bottom: parent.bottom
                        right: parent.right
                    }
                    width: parent.width * Math.max(0, Math.min(1, root.leftProximity))
                    radius: 4
                    color: Qt.rgba(root.leftColor.r,
                                   root.leftColor.g,
                                   root.leftColor.b, 0.6)

                    Behavior on width { NumberAnimation { duration: 100 } }
                    Behavior on color { ColorAnimation { duration: 200 } }
                }
            }
        }

        // ── Right bar ─────────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Text {
                text: "RIGHT"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 1.0
                color: Theme.Tokens.steel
                opacity: 0.7
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 20

                // Track
                Rectangle {
                    anchors.fill: parent
                    radius: 4
                    color: Qt.rgba(Theme.Tokens.chalk.r,
                                   Theme.Tokens.chalk.g,
                                   Theme.Tokens.chalk.b, 0.06)
                }

                // Fill (left-to-right)
                Rectangle {
                    anchors {
                        top: parent.top
                        bottom: parent.bottom
                        left: parent.left
                    }
                    width: parent.width * Math.max(0, Math.min(1, root.rightProximity))
                    radius: 4
                    color: Qt.rgba(root.rightColor.r,
                                   root.rightColor.g,
                                   root.rightColor.b, 0.6)

                    Behavior on width { NumberAnimation { duration: 100 } }
                    Behavior on color { ColorAnimation { duration: 200 } }
                }
            }
        }
    }
}
