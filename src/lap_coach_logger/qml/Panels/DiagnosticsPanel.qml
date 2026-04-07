import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../Theme" as Theme

Item {
    id: root

    signal backRequested()
    signal showAbout()

    ColumnLayout {
        anchors {
            fill: parent
            margins: Theme.Tokens.xl
        }
        spacing: Theme.Tokens.lg

        // Back button
        Rectangle {
            width: backRow.implicitWidth + 16
            height: 32
            radius: Theme.Tokens.radiusSm
            color: backArea.containsMouse
                   ? Theme.Tokens.subtle(Theme.Tokens.chalk, 0.10)
                   : "transparent"

            RowLayout {
                id: backRow
                anchors.centerIn: parent
                spacing: 4

                Text {
                    text: "\u2039"
                    font.pixelSize: 18
                    font.weight: Font.Bold
                    color: Theme.Tokens.pitOrange
                }

                Text {
                    text: "Settings"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.captionSize
                    color: Theme.Tokens.pitOrange
                }
            }

            MouseArea {
                id: backArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.backRequested()
            }
        }

        // Title
        Text {
            text: "Diagnostics"
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: 20
            font.weight: Font.Bold
            color: Theme.Tokens.chalk
        }

        // Log area
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.Tokens.radiusMd
            color: Theme.Tokens.raised
            border.width: 1
            border.color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08)

            ScrollView {
                anchors {
                    fill: parent
                    margins: Theme.Tokens.sm
                }
                clip: true

                TextArea {
                    id: logArea
                    readOnly: true
                    wrapMode: TextArea.Wrap
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 11
                    color: Theme.Tokens.steel
                    placeholderText: "No log events yet."
                    placeholderTextColor: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.25)
                    background: null
                    // Will be wired to serviceVM log events later
                }
            }
        }

        // Export Support Bundle button
        Rectangle {
            Layout.fillWidth: true
            height: 40
            radius: Theme.Tokens.radiusMd
            color: exportArea.containsMouse
                   ? Theme.Tokens.subtle(Theme.Tokens.chalk, 0.10)
                   : Theme.Tokens.subtle(Theme.Tokens.chalk)
            border.width: 1
            border.color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.12)

            Behavior on color {
                ColorAnimation { duration: Theme.Motion.hoverDuration }
            }

            Text {
                anchors.centerIn: parent
                text: "Export Support Bundle"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: 13
                font.weight: Font.DemiBold
                color: Theme.Tokens.chalk
            }

            MouseArea {
                id: exportArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    // Placeholder — will be wired later
                }
            }
        }

        // About link
        Rectangle {
            Layout.fillWidth: true
            height: 40
            radius: Theme.Tokens.radiusMd
            color: "transparent"

            Text {
                anchors.centerIn: parent
                text: "About Lap Coach"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: 13
                color: Theme.Tokens.pitOrange

                MouseArea {
                    id: aboutArea
                    anchors.fill: parent
                    anchors.margins: -8
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.showAbout()
                }
            }
        }
    }
}
