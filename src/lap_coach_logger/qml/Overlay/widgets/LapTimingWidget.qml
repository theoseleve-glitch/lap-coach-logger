import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  LapTimingWidget — compact lap timing overlay (280 x 120).
    Displays current lap time (large mono), last lap, best lap,
    and gap to leader in a simple 3-row layout.                  */
Rectangle {
    id: root
    width: 280
    height: 120
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property string currentTime: "-:---.---"
    property string lastTime: "-:---.---"
    property string bestTime: "-:---.---"
    property string gap: ""

    ColumnLayout {
        id: col
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 14
            rightMargin: 14
        }
        spacing: 0

        // ── Row 1: Current lap time (hero) ─────────────────────────
        ColumnLayout {
            spacing: 1

            Text {
                text: "CURRENT"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            Text {
                text: root.currentTime
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 28
                font.weight: Font.Bold
                color: Theme.Tokens.chalk
            }
        }

        // ── Divider ────────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 7
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

        // ── Row 2: Last + Best ─────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            ColumnLayout {
                spacing: 1
                Text {
                    text: "LAST"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    font.letterSpacing: 1.2
                    color: Theme.Tokens.steel
                }
                Text {
                    text: root.lastTime
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 13
                    font.weight: Font.Bold
                    color: Theme.Tokens.chalk
                }
            }

            Item { Layout.fillWidth: true }

            ColumnLayout {
                spacing: 1
                Layout.alignment: Qt.AlignRight
                Text {
                    text: "BEST"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    font.letterSpacing: 1.2
                    color: Theme.Tokens.steel
                    horizontalAlignment: Text.AlignRight
                    Layout.fillWidth: true
                }
                Text {
                    text: root.bestTime
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 13
                    font.weight: Font.Bold
                    color: Theme.Tokens.pitOrange
                    horizontalAlignment: Text.AlignRight
                    Layout.fillWidth: true
                }
            }
        }

        // ── Row 3: Gap to leader ───────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4
            visible: root.gap.length > 0

            Text {
                text: "GAP"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root.gap
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 13
                font.weight: Font.Bold
                color: Theme.Tokens.marshalYellow
            }
        }
    }
}
