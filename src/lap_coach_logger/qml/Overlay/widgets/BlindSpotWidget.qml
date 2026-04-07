import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  BlindSpotWidget -- left / right blind-spot indicators (200 x 90).
    Two large rectangles that flash when a car is alongside.
    Active  : filled with warning color + flash animation + arrow + label.
    Inactive: subtle dark background with "CLEAR" text.                   */
Rectangle {
    id: root
    width: 200
    height: 90
    color: "transparent"

    // -- public API ------------------------------------------------------
    property bool leftCar:  false
    property bool rightCar: false

    // -- inline component: reusable indicator ----------------------------
    component SpotIndicator: Rectangle {
        id: _ind

        required property bool carDetected
        required property string side          // "LEFT" | "RIGHT"

        readonly property string _arrow: side === "LEFT" ? "\u2190" : "\u2192"

        Layout.fillWidth:  true
        Layout.fillHeight: true
        radius: Theme.Tokens.radiusSm

        color: _ind.carDetected
               ? Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.30)
               : Theme.Tokens.subtle(Theme.Tokens.steel)
        border.width: 2
        border.color: _ind.carDetected
                      ? Theme.Tokens.medium(Theme.Tokens.safetyRed, 0.65)
                      : Theme.Tokens.subtle(Theme.Tokens.steel, 0.12)

        Behavior on color        { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
        Behavior on border.color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }

        // -- flash animation (driven by a separate property) -------------
        property real _flash: 1.0
        SequentialAnimation on _flash {
            running: _ind.carDetected
            loops:   Animation.Infinite
            NumberAnimation { to: 0.45; duration: 280; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1.00; duration: 280; easing.type: Easing.InOutSine }
        }
        opacity: _ind.carDetected ? _flash : 1.0

        // -- content -----------------------------------------------------
        ColumnLayout {
            anchors.centerIn: parent
            spacing: 1

            // Arrow + CAR label  /  side letter
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: _ind.carDetected
                      ? (_ind.side === "LEFT" ? _ind._arrow + " CAR" : "CAR " + _ind._arrow)
                      : _ind.side.charAt(0)
                font.family:    Theme.Typography.monoFamily
                font.pixelSize: _ind.carDetected ? 13 : 16
                font.weight:    Font.Bold
                color: _ind.carDetected ? Theme.Tokens.safetyRed : Theme.Tokens.steel
                opacity: _ind.carDetected ? 1.0 : 0.35

                Behavior on color   { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                Behavior on opacity { NumberAnimation { duration: Theme.Motion.statusColorDuration } }
            }

            // "CAR LEFT" / "CAR RIGHT" label  or  "CLEAR"
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: _ind.carDetected
                      ? "CAR " + _ind.side
                      : "CLEAR"
                font.family:    Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight:    Font.Bold
                font.letterSpacing: 0.8
                color: _ind.carDetected ? Theme.Tokens.marshalYellow : Theme.Tokens.steel
                opacity: _ind.carDetected ? 0.9 : 0.25

                Behavior on color   { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                Behavior on opacity { NumberAnimation { duration: Theme.Motion.statusColorDuration } }
            }
        }
    }

    // -- layout ----------------------------------------------------------
    ColumnLayout {
        anchors {
            fill: parent
            topMargin:    Theme.Tokens.sm
            bottomMargin: Theme.Tokens.sm
            leftMargin:   Theme.Tokens.md
            rightMargin:  Theme.Tokens.md
        }
        spacing: Theme.Tokens.xs

        // Header
        Text {
            text: "BLIND SPOT"
            font.family:       Theme.Typography.monoFamily
            font.pixelSize:    Theme.Typography.microSize
            font.weight:       Font.Bold
            font.letterSpacing: Theme.Typography.microSpacing
            color: Theme.Tokens.steel
            Layout.alignment: Qt.AlignHCenter
        }

        // Indicator pair
        RowLayout {
            Layout.fillWidth:  true
            Layout.fillHeight: true
            spacing: Theme.Tokens.sm

            SpotIndicator { carDetected: root.leftCar;  side: "LEFT"  }
            SpotIndicator { carDetected: root.rightCar; side: "RIGHT" }
        }
    }
}
