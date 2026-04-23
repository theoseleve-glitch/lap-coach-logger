import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  PushManageWidget — PUSH / MANAGE / SAVE decision (200 x 60).

    Single big word. That's it. In endurance you need at-a-glance "am
    I attacking or protecting right now?" and nothing else.

      PUSH   → green   (go)
      MANAGE → yellow  (ease, don't nurse)
      SAVE   → red     (fuel/grip are tight; conserve)

    Reason text appears smaller below for when the driver glances at a
    straight; auto-truncates if too long.                                */
Rectangle {
    id: root

    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 200
    height: 60
    color: "transparent"

    // -- public API -------------------------------------------------------
    property string state: "PUSH"     // "PUSH" / "MANAGE" / "SAVE"
    property string reason: ""

    // -- derived ----------------------------------------------------------
    readonly property color stateColor: {
        switch (state) {
        case "SAVE":   return Theme.Tokens.safetyRed
        case "MANAGE": return Theme.Tokens.marshalYellow
        default:       return Theme.Tokens.acidGreen
        }
    }

    // Background
    Rectangle {
        anchors.fill: parent
        radius: 8
        color: Qt.rgba(0, 0, 0, 0.82)
        border.width: 1
        border.color: Qt.rgba(root.stateColor.r, root.stateColor.g,
                              root.stateColor.b, 0.4)
        Behavior on border.color { ColorAnimation { duration: 200 } }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 0

        // The word
        Text {
            text: root.state
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(22 * root.fontScale)
            font.weight: Font.Black
            font.letterSpacing: 2.0
            color: root.stateColor
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            Behavior on color { ColorAnimation { duration: 200 } }
        }

        // Reason (tiny, muted)
        Text {
            text: root.reason
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(9 * root.fontScale)
            font.weight: Font.Medium
            color: Theme.Tokens.steel
            opacity: 0.7
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            elide: Text.ElideRight
            visible: root.reason.length > 0
        }
    }
}
