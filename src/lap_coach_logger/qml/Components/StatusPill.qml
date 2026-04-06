import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme

Rectangle {
    id: root

    property string status: "Idle"
    property string elapsed: ""

    readonly property color statusColor: {
        switch (status) {
        case "Recording":
            return Theme.Tokens.acidGreen
        case "Waiting":
        case "Simulator Detected":
            return Theme.Tokens.pitOrange
        case "Arming":
        case "Finalizing":
            return Theme.Tokens.marshalYellow
        case "Failed":
            return Theme.Tokens.safetyRed
        default:
            return Theme.Tokens.steel
        }
    }

    implicitWidth: pillRow.implicitWidth + Theme.Tokens.md * 2
    implicitHeight: 28
    radius: 20
    color: Theme.Tokens.subtle(statusColor, 0.08)
    border.width: 1
    border.color: Theme.Tokens.subtle(statusColor, 0.15)

    RowLayout {
        id: pillRow
        anchors.centerIn: parent
        spacing: Theme.Tokens.sm

        // Status dot
        Rectangle {
            id: statusDot
            width: 6
            height: 6
            radius: 3
            color: root.statusColor

            Behavior on color {
                ColorAnimation { duration: Theme.Motion.statusColorDuration }
            }

            // Recording pulse animation
            SequentialAnimation {
                id: pulseAnimation
                loops: Animation.Infinite
                running: root.status === "Recording"

                NumberAnimation {
                    target: statusDot
                    property: "opacity"
                    from: 1.0
                    to: 0.7
                    duration: Theme.Motion.recordingPulseDuration / 2
                }
                NumberAnimation {
                    target: statusDot
                    property: "opacity"
                    from: 0.7
                    to: 1.0
                    duration: Theme.Motion.recordingPulseDuration / 2
                }
            }

            // Reset opacity when not recording
            onVisibleChanged: if (!pulseAnimation.running) opacity = 1.0
            Connections {
                target: root
                function onStatusChanged() {
                    if (root.status !== "Recording")
                        statusDot.opacity = 1.0
                }
            }
        }

        // Status text
        Text {
            text: root.status
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: 11
            font.weight: Font.DemiBold
            color: Theme.Tokens.chalk
        }

        // Elapsed time (recording only)
        Text {
            visible: root.status === "Recording" && root.elapsed !== ""
            text: root.elapsed
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 10
            color: Theme.Tokens.steel
        }
    }

    // Recording glow effect
    layer.enabled: root.status === "Recording"
    layer.effect: Item {
        // Subtle glow via outer shadow emulation — real DropShadow needs
        // Qt5Compat.GraphicalEffects which may not be available. The 8% tint
        // on the pill background already conveys the recording state visually.
    }
}
