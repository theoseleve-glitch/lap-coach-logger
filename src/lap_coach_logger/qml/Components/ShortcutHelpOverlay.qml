import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme

Item {
    id: root
    anchors.fill: parent
    visible: false
    z: 999

    // Dim background
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.6)
        MouseArea { anchors.fill: parent; onClicked: root.visible = false }
    }

    // Help card
    Rectangle {
        z: 1
        anchors.centerIn: parent
        width: 380
        implicitHeight: col.implicitHeight + 48
        radius: 16
        color: Qt.rgba(0.04, 0.04, 0.055, 0.95)
        border.width: 1
        border.color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.08)

        // Top highlight
        Rectangle {
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 1; radius: 16
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.10) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }

        ColumnLayout {
            id: col
            anchors { fill: parent; margins: 24 }
            spacing: 16

            Text {
                text: "KEYBOARD SHORTCUTS"
                font { family: Theme.Typography.monoFamily; pixelSize: 11; weight: Font.Bold; letterSpacing: 2 }
                color: Theme.Tokens.pitOrange
            }

            // Shortcut list
            Column {
                Layout.fillWidth: true
                spacing: 6

                component ShortcutRow: RowLayout {
                    property string key: ""
                    property string desc: ""
                    Layout.fillWidth: true
                    spacing: 16
                    Text {
                        text: key
                        Layout.preferredWidth: 100
                        font { family: Theme.Typography.monoFamily; pixelSize: 12; weight: Font.Bold }
                        color: Theme.Tokens.pitOrange
                    }
                    Text {
                        text: desc
                        Layout.fillWidth: true
                        font { family: Theme.Typography.bodyFamily; pixelSize: 13 }
                        color: Theme.Tokens.chalk
                    }
                }

                ShortcutRow { key: "Ctrl+O"; desc: "Toggle overlay widgets" }
                ShortcutRow { key: "Ctrl+L"; desc: "Lock / unlock overlay positions" }
                ShortcutRow { key: "Ctrl+G"; desc: "Toggle snap-to-edge" }
                ShortcutRow { key: "Ctrl+H"; desc: "Toggle auto-hide on track" }
                ShortcutRow { key: "Ctrl+\u2191"; desc: "Increase overlay opacity" }
                ShortcutRow { key: "Ctrl+\u2193"; desc: "Decrease overlay opacity" }

                // Separator
                Rectangle {
                    width: parent.width; height: 1
                    color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.06)
                }

                ShortcutRow { key: "Ctrl+1"; desc: "Dashboard" }
                ShortcutRow { key: "Ctrl+2"; desc: "Live telemetry" }
                ShortcutRow { key: "Ctrl+3"; desc: "Session history" }
                ShortcutRow { key: "Ctrl+4"; desc: "Overlay manager" }

                Rectangle {
                    width: parent.width; height: 1
                    color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.06)
                }

                ShortcutRow { key: "Alt+1-9"; desc: "Quick-toggle overlay widgets" }
                ShortcutRow { key: "Escape"; desc: "Close settings / help" }
                ShortcutRow { key: "F1"; desc: "This help" }
            }

            // Close hint
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "Press F1 or Escape to close"
                font { family: Theme.Typography.monoFamily; pixelSize: 10 }
                color: Theme.Tokens.steel
                opacity: 0.5
            }
        }
    }

    // Animations
    opacity: visible ? 1.0 : 0.0
    Behavior on opacity { NumberAnimation { duration: 200 } }
}
