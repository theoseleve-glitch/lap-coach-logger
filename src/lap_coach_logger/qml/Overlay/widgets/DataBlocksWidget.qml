import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  DataBlocksWidget — compact configurable data blocks (320x200).
    Each block is a labeled value displayed in a 2- or 3-column grid. */
Rectangle {
    id: root
    width: 320
    height: 200
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property var blocks: [
        { label: "SPEED",    value: "---", color: "" },
        { label: "GEAR",     value: "-",   color: "" },
        { label: "RPM",      value: "---", color: "" },
        { label: "THROTTLE", value: "---", color: "" },
        { label: "BRAKE",    value: "---", color: "" },
        { label: "DELTA",    value: "---", color: "" }
    ]

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 12
            rightMargin: 12
        }
        spacing: 0

        // ── Header ─────────────────────────────────────────────────
        Text {
            text: "DATA BLOCKS"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 9
            font.weight: Font.Bold
            font.letterSpacing: 1.2
            color: Theme.Tokens.steel
        }

        // ── Separator ──────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 8
            Rectangle {
                anchors.centerIn: parent
                width: parent.width; height: 1
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

        // ── Blocks grid (3 columns) ───────────────────────────────
        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 3
            rowSpacing: 6
            columnSpacing: 6

            Repeater {
                model: root.blocks.length

                delegate: Rectangle {
                    required property int index
                    Layout.fillWidth: true
                    Layout.preferredHeight: 52
                    radius: 6
                    color: Qt.rgba(Theme.Tokens.chalk.r,
                                   Theme.Tokens.chalk.g,
                                   Theme.Tokens.chalk.b, 0.04)
                    border.width: 1
                    border.color: Qt.rgba(Theme.Tokens.chalk.r,
                                          Theme.Tokens.chalk.g,
                                          Theme.Tokens.chalk.b, 0.04)

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 2

                        Text {
                            text: {
                                var b = root.blocks[index]
                                return b ? b.label : ""
                            }
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: 7
                            font.weight: Font.Bold
                            font.letterSpacing: 0.8
                            color: Theme.Tokens.steel
                            Layout.alignment: Qt.AlignHCenter
                        }

                        Text {
                            text: {
                                var b = root.blocks[index]
                                return b ? b.value : ""
                            }
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: 16
                            font.weight: Font.Bold
                            color: {
                                var b = root.blocks[index]
                                return (b && b.color) ? b.color : Theme.Tokens.chalk
                            }
                            Layout.alignment: Qt.AlignHCenter
                        }
                    }
                }
            }
        }
    }
}
