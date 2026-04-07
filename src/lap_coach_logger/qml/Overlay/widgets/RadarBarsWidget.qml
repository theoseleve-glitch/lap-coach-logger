import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  RadarBarsWidget -- horizontal proximity bars (200 x 120).
    Left bar fills from right edge, right bar fills from left edge.
    Danger state shifts to safetyRed + flash, text labels for
    CLEAR / CAR LEFT / CAR RIGHT, center divider, percentage.      */
Rectangle {
    id: root
    width: 200
    height: 120
    color: "transparent"

    // -- public API ----------------------------------------------------------
    property real leftProximity:  0.0    // 0..1
    property real rightProximity: 0.0    // 0..1
    property bool leftDanger:    false
    property bool rightDanger:   false

    // -- null-safe clamped values -------------------------------------------
    readonly property real safeLeft:  Math.max(0, Math.min(1, leftProximity || 0))
    readonly property real safeRight: Math.max(0, Math.min(1, rightProximity || 0))

    // -- color derivation ---------------------------------------------------
    readonly property color leftColor:  leftDanger
        ? Theme.Tokens.safetyRed : Theme.Tokens.pitOrange
    readonly property color rightColor: rightDanger
        ? Theme.Tokens.safetyRed : Theme.Tokens.pitOrange

    // -- status labels ------------------------------------------------------
    readonly property string leftLabel: {
        if (safeLeft < 0.01) return "CLEAR"
        if (leftDanger)      return "DANGER"
        return "CAR LEFT"
    }
    readonly property string rightLabel: {
        if (safeRight < 0.01) return "CLEAR"
        if (rightDanger)      return "DANGER"
        return "CAR RIGHT"
    }

    // -- danger flash animation ---------------------------------------------
    property real _flashOpacity: 1.0

    SequentialAnimation on _flashOpacity {
        running: leftDanger || rightDanger
        loops: Animation.Infinite
        NumberAnimation { from: 1.0; to: 0.4; duration: 200;
                          easing.type: Easing.InOutSine }
        NumberAnimation { from: 0.4; to: 1.0; duration: 200;
                          easing.type: Easing.InOutSine }
    }

    onLeftDangerChanged:  if (!leftDanger && !rightDanger) _flashOpacity = 1.0
    onRightDangerChanged: if (!leftDanger && !rightDanger) _flashOpacity = 1.0

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 12
            rightMargin: 12
        }
        spacing: 6

        // -- Header ----------------------------------------------------------
        Text {
            text: "PROXIMITY"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 9
            font.weight: Font.Bold
            font.letterSpacing: 1.2
            color: Theme.Tokens.steel
        }

        // -- Left bar section ------------------------------------------------
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            RowLayout {
                Layout.fillWidth: true
                spacing: 4

                Text {
                    text: root.leftLabel
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.Bold
                    font.letterSpacing: 1.0
                    color: safeLeft < 0.01
                           ? Theme.Tokens.steel
                           : root.leftColor
                    opacity: leftDanger ? root._flashOpacity : 0.9

                    Behavior on color { ColorAnimation { duration: 200 } }
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: Math.round(root.safeLeft * 100) + "%"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.DemiBold
                    color: Theme.Tokens.steel
                    opacity: safeLeft > 0.01 ? 0.8 : 0.3
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 20

                // Track
                Rectangle {
                    anchors.fill: parent
                    radius: 4
                    color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.06)
                }

                // Fill (right-to-left: anchored to right edge)
                Rectangle {
                    anchors {
                        top: parent.top
                        bottom: parent.bottom
                        right: parent.right
                    }
                    width: parent.width * root.safeLeft
                    radius: 4
                    color: Qt.rgba(root.leftColor.r, root.leftColor.g,
                                   root.leftColor.b, 0.6)
                    opacity: leftDanger ? root._flashOpacity : 1.0

                    Behavior on width { NumberAnimation {
                        duration: 120; easing.type: Easing.OutCubic } }
                    Behavior on color { ColorAnimation { duration: 200 } }
                }
            }
        }

        // -- Center divider --------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.Tokens.subtle(Theme.Tokens.steel, 0.12)
        }

        // -- Right bar section -----------------------------------------------
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            RowLayout {
                Layout.fillWidth: true
                spacing: 4

                Text {
                    text: root.rightLabel
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.Bold
                    font.letterSpacing: 1.0
                    color: safeRight < 0.01
                           ? Theme.Tokens.steel
                           : root.rightColor
                    opacity: rightDanger ? root._flashOpacity : 0.9

                    Behavior on color { ColorAnimation { duration: 200 } }
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: Math.round(root.safeRight * 100) + "%"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.DemiBold
                    color: Theme.Tokens.steel
                    opacity: safeRight > 0.01 ? 0.8 : 0.3
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 20

                // Track
                Rectangle {
                    anchors.fill: parent
                    radius: 4
                    color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.06)
                }

                // Fill (left-to-right: anchored to left edge)
                Rectangle {
                    anchors {
                        top: parent.top
                        bottom: parent.bottom
                        left: parent.left
                    }
                    width: parent.width * root.safeRight
                    radius: 4
                    color: Qt.rgba(root.rightColor.r, root.rightColor.g,
                                   root.rightColor.b, 0.6)
                    opacity: rightDanger ? root._flashOpacity : 1.0

                    Behavior on width { NumberAnimation {
                        duration: 120; easing.type: Easing.OutCubic } }
                    Behavior on color { ColorAnimation { duration: 200 } }
                }
            }
        }
    }
}
