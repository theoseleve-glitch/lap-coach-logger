import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  FuelCalculatorWidget -- extended fuel strategy display (220x200).
    Shows current fuel, consumption rate, laps remaining,
    fuel to add at pit, stint length and target.
    Color tiers: green=safe, yellow=tight, orange=save, red=box.     */
Rectangle {
    id: root
    width: 220
    height: 200
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real fuelLevel: 0.0
    property real fuelPerLap: 0.0
    property real lapsLeft: 0.0
    property real fuelToAdd: 0.0
    property int  stintLaps: 0
    property int  targetLaps: 0

    // ── null-safe helpers ───────────────────────────────────────────
    function safeFix(v, d) { return isFinite(v) ? v.toFixed(d) : "--" }
    function safeInt(v)    { return isFinite(v) ? v : 0 }
    readonly property real safeLapsLeft: isFinite(lapsLeft) ? lapsLeft : 0
    readonly property real safeFuelToAdd: isFinite(fuelToAdd) ? Math.max(0, fuelToAdd) : 0
    readonly property bool needsFuel: safeFuelToAdd > 0

    // ── 4-tier fuel state color ─────────────────────────────────────
    readonly property color stateColor: {
        if (safeLapsLeft < 1.0) return Theme.Tokens.safetyRed      // BOX NOW
        if (safeLapsLeft < 3.0) return Theme.Tokens.pitOrange      // FUEL SAVE
        if (safeLapsLeft < 5.0) return Theme.Tokens.marshalYellow  // TIGHT
        return Theme.Tokens.acidGreen                               // SAFE
    }
    readonly property string stateLabel: {
        if (safeLapsLeft < 1.0) return "BOX"
        if (safeLapsLeft < 3.0) return "SAVE"
        if (safeLapsLeft < 5.0) return "TIGHT"
        return "OK"
    }

    // ── target comparison ───────────────────────────────────────────
    readonly property color targetColor: {
        var remaining = safeInt(targetLaps) - safeInt(stintLaps)
        if (remaining <= 0) return Theme.Tokens.acidGreen
        if (remaining <= 3) return Theme.Tokens.marshalYellow
        return Theme.Tokens.chalk
    }

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
                text: "FUEL CALC"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Theme.Typography.microWeight
                font.letterSpacing: Theme.Typography.microSpacing
                color: Theme.Tokens.steel
            }

            // State badge
            Rectangle {
                implicitWidth: fuelStateLabel.implicitWidth + 10
                implicitHeight: 14
                radius: 3
                color: Theme.Tokens.subtle(root.stateColor, 0.12)
                border.width: 1
                border.color: Theme.Tokens.subtle(root.stateColor, 0.25)

                Behavior on color        { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                Behavior on border.color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }

                Text {
                    id: fuelStateLabel
                    anchors.centerIn: parent
                    text: root.stateLabel
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                    color: root.stateColor
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

            DataRow { label: "FUEL LEVEL"; value: root.safeFix(root.fuelLevel, 1) + " L" }
            DataRow { label: "FUEL / LAP"; value: root.safeFix(root.fuelPerLap, 2) + " L" }
            DataRow {
                label: "LAPS LEFT"
                value: root.safeFix(root.safeLapsLeft, 1)
                valueColor: root.stateColor
            }

            GradientSep { Layout.preferredHeight: 6 }

            // Fuel to add -- prominent when needed
            DataRow {
                label: "FUEL TO ADD"
                value: root.safeFix(root.safeFuelToAdd, 1) + " L"
                valueColor: Theme.Tokens.pitOrange
                prominent: root.needsFuel
            }
            DataRow {
                label: "STINT"
                value: root.safeInt(root.stintLaps) + " laps"
            }
            DataRow {
                label: "TARGET"
                value: root.safeInt(root.targetLaps) + " laps"
                valueColor: root.targetColor
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
