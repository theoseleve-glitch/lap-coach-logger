import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme

Rectangle {
    id: root

    property bool active: false
    property int currentLap: 0
    property int totalLaps: 0
    property string phase: ""
    property string momentTitle: ""

    visible: active
    anchors.horizontalCenter: parent.horizontalCenter
    y: active ? 12 : -height
    width: Math.min(parent.width - 48, 640)
    height: content.implicitHeight + 16
    radius: Theme.Tokens.radiusMd
    color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.18)
    border.width: 1
    border.color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.40)
    z: 90

    Behavior on y { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

    RowLayout {
        id: content
        anchors {
            left: parent.left; right: parent.right
            verticalCenter: parent.verticalCenter
            leftMargin: Theme.Tokens.lg; rightMargin: Theme.Tokens.lg
        }
        spacing: Theme.Tokens.md

        // Pulsing dot
        Rectangle {
            width: 10; height: 10; radius: 5
            color: Theme.Tokens.racingPurple
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                NumberAnimation { from: 1.0; to: 0.3; duration: 800 }
                NumberAnimation { from: 0.3; to: 1.0; duration: 800 }
            }
        }

        Text {
            text: "DEMO MODE"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.microSize
            font.weight: Font.Bold; font.letterSpacing: 2.0
            color: Theme.Tokens.racingPurple
        }

        Rectangle {
            width: 1; height: 14
            color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.30)
        }

        Text {
            text: "SYNTHETIC DATA"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.microSize
            font.weight: Font.Bold; font.letterSpacing: 1.2
            color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.7)
        }

        Item { Layout.fillWidth: true }

        Text {
            visible: root.totalLaps > 0
            text: "LAP " + root.currentLap + "/" + root.totalLaps
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.microSize
            font.weight: Font.Bold
            color: Theme.Tokens.chalk
        }

        Text {
            visible: root.phase !== ""
            text: root.phase.toUpperCase()
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.microSize
            font.weight: Font.Bold; font.letterSpacing: 1.2
            color: Theme.Tokens.racingPurple
        }
    }
}
