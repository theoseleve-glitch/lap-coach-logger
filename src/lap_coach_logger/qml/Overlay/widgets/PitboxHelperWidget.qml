import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  PitboxHelperWidget -- pit stop planning display (240x160).
    Shows estimated pit entry lap, fuel to add, tire change
    recommendation, and pit time estimate.
    PIT WINDOW badge: green OPEN / red CLOSED with glow animation.   */
Rectangle {
    id: root
    width: 240
    height: 160
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property int    pitLap: 0
    property real   fuelToAdd: 0.0
    property bool   tireChange: false
    property string estimatedPitTime: "--"
    property bool   pitWindowOpen: false

    // ── null-safe helpers ───────────────────────────────────────────
    readonly property int    safePitLap: isFinite(pitLap) ? pitLap : 0
    readonly property real   safeFuelToAdd: isFinite(fuelToAdd) ? Math.max(0, fuelToAdd) : 0
    readonly property string safePitTime: (typeof estimatedPitTime === "string" && estimatedPitTime.length > 0)
                                           ? estimatedPitTime : "--"
    readonly property bool   needsFuel: safeFuelToAdd > 0

    // ── derived colors ──────────────────────────────────────────────
    readonly property color windowColor: pitWindowOpen
                                         ? Theme.Tokens.acidGreen
                                         : Theme.Tokens.safetyRed
    readonly property color tireColor: tireChange
                                       ? Theme.Tokens.marshalYellow
                                       : Theme.Tokens.acidGreen

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: Theme.Tokens.md
            bottomMargin: Theme.Tokens.md
            leftMargin: Theme.Tokens.md
            rightMargin: Theme.Tokens.md
        }
        spacing: 0

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "PITBOX"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Theme.Typography.microWeight
                font.letterSpacing: Theme.Typography.microSpacing
                color: Theme.Tokens.steel
            }

            // Pit window badge with animated glow
            Rectangle {
                id: windowBadge
                implicitWidth: windowLabel.implicitWidth + 12
                implicitHeight: 16
                radius: 4
                color: Theme.Tokens.subtle(root.windowColor, 0.12)
                border.width: 1
                border.color: Theme.Tokens.subtle(root.windowColor, 0.25)

                Behavior on color        { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                Behavior on border.color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }

                // Glow pulse when OPEN
                property real glowOpacity: 0
                SequentialAnimation on glowOpacity {
                    running: root.pitWindowOpen
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.35; duration: Theme.Motion.recordingPulseDuration; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.10; duration: Theme.Motion.recordingPulseDuration; easing.type: Easing.InOutSine }
                }

                Rectangle {
                    anchors.fill: parent
                    radius: parent.radius
                    color: root.windowColor
                    opacity: root.pitWindowOpen ? windowBadge.glowOpacity : 0
                    visible: root.pitWindowOpen
                }

                Text {
                    id: windowLabel
                    anchors.centerIn: parent
                    text: root.pitWindowOpen ? "OPEN" : "CLOSED"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                    color: root.windowColor
                    Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                }
            }

            Item { Layout.fillWidth: true }
        }

        // ── Separator ──────────────────────────────────────────────
        GradientSep {}

        // ── Data rows ──────────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6

            DataRow {
                label: "PIT LAP"
                value: root.safePitLap > 0 ? ("L" + root.safePitLap) : "--"
            }

            DataRow {
                label: "FUEL ADD"
                value: root.safeFuelToAdd.toFixed(1) + " L"
                valueColor: Theme.Tokens.pitOrange
                prominent: root.needsFuel
            }

            GradientSep { Layout.preferredHeight: 6 }

            DataRow {
                label: "TYRES"
                value: root.tireChange ? "CHANGE" : "KEEP"
                valueColor: root.tireColor
            }

            DataRow {
                label: "PIT TIME"
                value: root.safePitTime
            }
        }
    }

    // ── Gradient separator component ───────────────────────────────
    component GradientSep: Item {
        Layout.fillWidth: true
        Layout.preferredHeight: 8
        Rectangle {
            anchors.centerIn: parent
            width: parent.width; height: 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }
    }

    // ── Reusable data row ──────────────────────────────────────────
    component DataRow: RowLayout {
        property string label
        property string value
        property color  valueColor: Theme.Tokens.chalk
        property bool   prominent: false

        Layout.fillWidth: true

        Text {
            text: label
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.microSize
            font.weight: Theme.Typography.microWeight
            font.letterSpacing: 1.0
            color: Theme.Tokens.steel
        }
        Item { Layout.fillWidth: true }
        Text {
            text: value
            font.family: Theme.Typography.monoFamily
            font.pixelSize: prominent ? 16 : 13
            font.weight: Font.Bold
            color: valueColor
            Behavior on color     { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
            Behavior on font.pixelSize { NumberAnimation { duration: 150 } }
        }
    }
}
