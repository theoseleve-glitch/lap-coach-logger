import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  OvertakeAlertWidget -- overtake / defend alert banner (240 x 60).
    Shows "OVERTAKE" (green) or "DEFEND" (red) with directional arrows
    and optional car-number badge.  Pulses when active, fades when idle. */
Rectangle {
    id: root
    width:  240
    height: 60
    color: "transparent"

    // -- public API ------------------------------------------------------
    //   "none" | "overtake_left" | "overtake_right"
    //          | "defend_left"   | "defend_right"
    property string alertType:  "none"
    property string carNumber:  ""

    // -- derived (null-safe) ---------------------------------------------
    readonly property bool   _active:    typeof alertType === "string" && alertType !== "none"
    readonly property bool   _overtake:  typeof alertType === "string" && alertType.indexOf("overtake") === 0
    readonly property bool   _defend:    typeof alertType === "string" && alertType.indexOf("defend") === 0
    readonly property bool   _left:      typeof alertType === "string" && alertType.indexOf("_left") !== -1
    readonly property string _label:     _overtake ? "OVERTAKE" : (_defend ? "DEFEND" : "")
    readonly property string _arrow:     _left ? "\u25C4" : "\u25BA"
    readonly property color  _color: {
        if (_overtake) return Theme.Tokens.acidGreen
        if (_defend)   return Theme.Tokens.safetyRed
        return Theme.Tokens.steel
    }
    readonly property bool _hasNumber: typeof carNumber === "string" && carNumber.length > 0

    // -- alert panel -----------------------------------------------------
    Rectangle {
        id: panel
        anchors { fill: parent; margins: Theme.Tokens.xs }
        radius: Theme.Tokens.radiusSm

        color: root._active
               ? Theme.Tokens.subtle(root._color, 0.18)
               : Theme.Tokens.subtle(Theme.Tokens.steel)
        border.width: root._active ? 2 : 1
        border.color: root._active
                      ? Theme.Tokens.medium(root._color, 0.55)
                      : Theme.Tokens.subtle(Theme.Tokens.steel, 0.10)

        Behavior on color        { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
        Behavior on border.color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }

        // -- fade / pulse ------------------------------------------------
        property real _pulse: 1.0
        SequentialAnimation on _pulse {
            running: root._active
            loops:   Animation.Infinite
            NumberAnimation { to: 0.55; duration: 380; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1.00; duration: 380; easing.type: Easing.InOutSine }
        }

        // Fade out smoothly when inactive
        opacity: root._active ? _pulse : 0.6
        Behavior on opacity { NumberAnimation { duration: Theme.Motion.statusColorDuration } }

        // Scale bump on activation
        scale: root._active ? 1.0 : 0.97
        Behavior on scale { NumberAnimation { duration: Theme.Motion.statusColorDuration; easing.type: Easing.OutBack } }

        // -- content row -------------------------------------------------
        RowLayout {
            anchors.centerIn: parent
            spacing: Theme.Tokens.sm

            // Left arrow (visible only when direction is left)
            Text {
                visible: root._active && root._left
                text:    root._arrow
                font.pixelSize: 18
                font.weight: Font.Bold
                color: root._color
                Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
            }

            // Alert label
            Text {
                text: root._active ? root._label : "NO ALERT"
                font.family:       Theme.Typography.monoFamily
                font.pixelSize:    root._active ? 18 : 11
                font.weight:       Font.Bold
                font.letterSpacing: root._active ? 2.0 : 1.2
                color:   root._active ? root._color : Theme.Tokens.steel
                opacity: root._active ? 1.0 : 0.4

                Behavior on color   { ColorAnimation  { duration: Theme.Motion.statusColorDuration } }
                Behavior on opacity { NumberAnimation  { duration: Theme.Motion.statusColorDuration } }
            }

            // Car number badge
            Rectangle {
                visible: root._active && root._hasNumber
                width:   _numText.implicitWidth + Theme.Tokens.md
                height:  22
                radius:  Theme.Tokens.xs
                color:   Theme.Tokens.subtle(root._color, 0.22)

                Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }

                Text {
                    id: _numText
                    anchors.centerIn: parent
                    text: "#" + (root.carNumber || "")
                    font.family:    Theme.Typography.monoFamily
                    font.pixelSize: 11
                    font.weight:    Font.Bold
                    color: root._color

                    Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                }
            }

            // Right arrow (visible only when direction is right)
            Text {
                visible: root._active && !root._left
                text:    root._arrow
                font.pixelSize: 18
                font.weight: Font.Bold
                color: root._color
                Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
            }
        }
    }
}
