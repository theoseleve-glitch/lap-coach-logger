import QtQuick
import "../Theme" as Theme

Item {
    id: root

    property bool checked: false

    signal toggled(bool checked)

    implicitWidth: 44
    implicitHeight: 24

    // Track
    Rectangle {
        id: track
        anchors.fill: parent
        radius: height / 2
        color: root.checked ? Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.30)
                            : Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08)
        border.width: 1
        border.color: root.checked ? Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.40)
                                   : Theme.Tokens.subtle(Theme.Tokens.chalk, 0.12)

        Behavior on color {
            ColorAnimation { duration: Theme.Motion.hoverDuration }
        }
        Behavior on border.color {
            ColorAnimation { duration: Theme.Motion.hoverDuration }
        }
    }

    // Knob
    Rectangle {
        id: knob
        width: 18
        height: 18
        radius: 9
        y: (root.height - height) / 2
        x: root.checked ? root.width - width - 3 : 3
        color: root.checked ? Theme.Tokens.acidGreen : "#646464"

        Behavior on x {
            NumberAnimation {
                duration: Theme.Motion.hoverDuration
                easing.type: Easing.OutBack
            }
        }
        Behavior on color {
            ColorAnimation { duration: Theme.Motion.hoverDuration }
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            root.checked = !root.checked
            root.toggled(root.checked)
        }
    }
}
