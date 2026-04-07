import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  AdvancedPanelWidget — multi-row configurable telemetry panel (360x280).
    Grid of label+value+unit pairs drawn from a channel list.
    Default channels: speed, rpm, gear, brake temp, tyre temp, fuel, pos, gap. */
Rectangle {
    id: root
    width: 360
    height: 280
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property var channels: [
        { label: "SPEED",      value: "---",  unit: "km/h", color: "" },
        { label: "RPM",        value: "---",  unit: "",     color: "" },
        { label: "GEAR",       value: "-",    unit: "",     color: "" },
        { label: "BRK TEMP",   value: "---",  unit: "C",    color: "" },
        { label: "TYRE TEMP",  value: "---",  unit: "C",    color: "" },
        { label: "FUEL",       value: "---",  unit: "L",    color: "" },
        { label: "POSITION",   value: "-",    unit: "",     color: "" },
        { label: "GAP",        value: "---",  unit: "s",    color: "" }
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
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "DATA PANEL"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            Rectangle {
                implicitWidth: countLabel.implicitWidth + 8
                implicitHeight: 14
                radius: 3
                color: Qt.rgba(Theme.Tokens.pitOrange.r,
                               Theme.Tokens.pitOrange.g,
                               Theme.Tokens.pitOrange.b, 0.12)

                Text {
                    id: countLabel
                    anchors.centerIn: parent
                    text: root.channels.length + " CH"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    font.weight: Font.Bold
                    color: Theme.Tokens.pitOrange
                }
            }

            Item { Layout.fillWidth: true }
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

        // ── Channel grid (2 columns) ──────────────────────────────
        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 2
            rowSpacing: 4
            columnSpacing: 12

            Repeater {
                model: root.channels.length

                delegate: Rectangle {
                    required property int index
                    Layout.fillWidth: true
                    Layout.preferredHeight: 28
                    radius: 4
                    color: Qt.rgba(Theme.Tokens.chalk.r,
                                   Theme.Tokens.chalk.g,
                                   Theme.Tokens.chalk.b, 0.03)

                    RowLayout {
                        anchors {
                            fill: parent
                            leftMargin: 8
                            rightMargin: 8
                        }
                        spacing: 4

                        Text {
                            text: {
                                var ch = root.channels[index]
                                return ch ? ch.label : ""
                            }
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: 8
                            font.weight: Font.Bold
                            font.letterSpacing: 0.8
                            color: Theme.Tokens.steel
                            Layout.preferredWidth: 60
                        }

                        Item { Layout.fillWidth: true }

                        Text {
                            text: {
                                var ch = root.channels[index]
                                if (!ch) return ""
                                return ch.value + (ch.unit ? " " + ch.unit : "")
                            }
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: {
                                var ch = root.channels[index]
                                return (ch && ch.color) ? ch.color : Theme.Tokens.chalk
                            }
                            horizontalAlignment: Text.AlignRight
                        }
                    }
                }
            }
        }
    }
}
