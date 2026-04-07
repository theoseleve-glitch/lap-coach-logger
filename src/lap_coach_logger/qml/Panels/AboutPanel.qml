import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../Theme" as Theme

Item {
    id: root

    signal backRequested()

    Flickable {
        anchors.fill: parent
        contentHeight: aboutColumn.implicitHeight + 56
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        ColumnLayout {
            id: aboutColumn
            anchors {
                left: parent.left
                right: parent.right
                top: parent.top
                leftMargin: 28
                rightMargin: 28
                topMargin: 28
            }
            spacing: Theme.Tokens.lg

            // Back button
            Rectangle {
                width: aboutBackRow.implicitWidth + 16
                height: 32
                radius: Theme.Tokens.radiusSm
                color: aboutBackArea.containsMouse
                       ? Theme.Tokens.subtle(Theme.Tokens.chalk, 0.10)
                       : "transparent"

                RowLayout {
                    id: aboutBackRow
                    anchors.centerIn: parent
                    spacing: 4

                    Text {
                        text: "\u2039"
                        font.pixelSize: 18
                        font.weight: Font.Bold
                        color: Theme.Tokens.pitOrange
                    }

                    Text {
                        text: "Diagnostics"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.captionSize
                        color: Theme.Tokens.pitOrange
                    }
                }

                MouseArea {
                    id: aboutBackArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.backRequested()
                }
            }

            // Monogram placeholder
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Theme.Tokens.sm
                width: 64
                height: 64
                radius: Theme.Tokens.radiusLg
                color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.15)
                border.width: 1
                border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.25)

                Text {
                    anchors.centerIn: parent
                    text: "LC"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: 22
                    font.weight: Font.Bold
                    color: Theme.Tokens.pitOrange
                }
            }

            // App name
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "LAP COACH"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: 22
                font.weight: Font.Bold
                font.letterSpacing: 3
                color: Theme.Tokens.chalk
            }

            // Subtitle
            Text {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: -10
                text: "TELEMETRY LOGGER"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Font.DemiBold
                font.letterSpacing: 2
                color: Theme.Tokens.pitOrange
            }

            // Version
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "v1.1.0"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.captionSize
                color: Theme.Tokens.steel
            }

            // Separator
            Rectangle {
                Layout.fillWidth: true
                Layout.topMargin: Theme.Tokens.sm
                height: 1
                color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.12)
            }

            // Info card
            Rectangle {
                Layout.fillWidth: true
                Layout.topMargin: Theme.Tokens.xs
                radius: Theme.Tokens.radiusLg
                color: Theme.Tokens.surface
                border.width: 1
                border.color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08)
                implicitHeight: infoColumn.implicitHeight + 32

                ColumnLayout {
                    id: infoColumn
                    anchors {
                        left: parent.left
                        right: parent.right
                        top: parent.top
                        margins: Theme.Tokens.lg
                    }
                    spacing: Theme.Tokens.md

                    // Description
                    Text {
                        Layout.fillWidth: true
                        text: "Local-first telemetry capture.\nNo cloud sync. No account. No nonsense."
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.captionSize
                        color: Theme.Tokens.steel
                        wrapMode: Text.WordWrap
                        lineHeight: 1.4
                    }

                    // Info separator
                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08)
                    }

                    // Label-value rows
                    Repeater {
                        model: [
                            { label: "PUBLISHER", value: "Lap Coach" },
                            { label: "INSTALL PATH", value: Qt.application.arguments[0] || "N/A" },
                            { label: "CONFIG PATH", value: settingsVM ? settingsVM.getString("config_path") : "N/A" },
                            { label: "LOG PATH", value: settingsVM ? settingsVM.getString("log_path") : "N/A" }
                        ]

                        delegate: ColumnLayout {
                            required property var modelData
                            required property int index

                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                text: modelData.label
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Theme.Typography.microWeight
                                font.letterSpacing: 1.5
                                color: Theme.Tokens.pitOrange
                            }

                            Text {
                                Layout.fillWidth: true
                                text: modelData.value
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: 11
                                color: Theme.Tokens.chalk
                                elide: Text.ElideMiddle
                            }
                        }
                    }
                }
            }
        }
    }
}
