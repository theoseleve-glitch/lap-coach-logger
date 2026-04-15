import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme

Rectangle {
    id: root

    property bool active: false
    property bool playing: false

    signal playRequested()
    signal pauseRequested()
    signal stepRequested()
    signal resetRequested()

    visible: active
    width: controls.implicitWidth + Theme.Tokens.lg * 2
    height: 44
    radius: Theme.Tokens.radiusMd
    color: Theme.Tokens.elevated
    border.width: 1
    border.color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.25)

    component CtlButton: Rectangle {
        required property string label
        required property color accentColor
        signal clicked()
        property bool hovered: ctlArea.containsMouse
        width: ctlText.implicitWidth + Theme.Tokens.md * 2
        height: 30
        radius: Theme.Tokens.radiusSm
        color: hovered ? Theme.Tokens.subtle(accentColor, 0.20) : Theme.Tokens.subtle(accentColor, 0.10)
        border.width: 1
        border.color: Theme.Tokens.subtle(accentColor, 0.30)
        Text {
            id: ctlText
            anchors.centerIn: parent
            text: parent.label
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.microSize
            font.weight: Font.Bold; font.letterSpacing: 1.0
            color: parent.accentColor
        }
        MouseArea {
            id: ctlArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: parent.clicked()
        }
    }

    RowLayout {
        id: controls
        anchors { fill: parent; margins: Theme.Tokens.md }
        spacing: Theme.Tokens.sm

        CtlButton {
            label: root.playing ? "PAUSE" : "PLAY"
            accentColor: root.playing ? Theme.Tokens.marshalYellow : Theme.Tokens.acidGreen
            onClicked: {
                if (root.playing) root.pauseRequested()
                else root.playRequested()
            }
        }

        CtlButton {
            label: "STEP"
            accentColor: Theme.Tokens.chalk
            onClicked: root.stepRequested()
        }

        CtlButton {
            label: "RESET"
            accentColor: Theme.Tokens.steel
            onClicked: root.resetRequested()
        }
    }
}
