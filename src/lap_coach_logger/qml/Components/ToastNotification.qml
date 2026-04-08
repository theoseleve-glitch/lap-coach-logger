import QtQuick
import "../Theme" as Theme

// Brief popup notification at the bottom of the screen.
// Call show("message") to display, auto-hides after 2.5 seconds.

Rectangle {
    id: root
    anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 60 }
    width: toastText.implicitWidth + 40
    height: 36
    radius: 18
    color: Qt.rgba(Theme.Tokens.surface.r, Theme.Tokens.surface.g, Theme.Tokens.surface.b, 0.92)
    border.width: 1
    border.color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.10)
    visible: opacity > 0
    opacity: 0
    z: 998

    Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.InOutQuad } }

    Text {
        id: toastText
        anchors.centerIn: parent
        text: ""
        font { family: Theme.Typography.monoFamily; pixelSize: 12; weight: Font.DemiBold }
        color: Theme.Tokens.chalk
    }

    Timer {
        id: hideTimer
        interval: 2500
        onTriggered: root.opacity = 0
    }

    function show(message) {
        toastText.text = message
        root.opacity = 1
        hideTimer.restart()
    }
}
