import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  FuelCalculatorWidget — extended fuel strategy display (220x200).
    Shows current fuel, consumption rate, laps remaining,
    fuel to add at pit, stint length and target.                    */
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

    // ── derived ─────────────────────────────────────────────────────
    readonly property color stateColor: {
        if (root.lapsLeft < 2.0) return Theme.Tokens.safetyRed
        if (root.lapsLeft < 5.0) return Theme.Tokens.marshalYellow
        return Theme.Tokens.acidGreen
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 12
            rightMargin: 12
        }
        spacing: 0

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "FUEL CALC"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            Rectangle {
                width: 5; height: 5; radius: 2.5
                color: root.stateColor
                Layout.alignment: Qt.AlignVCenter
                Behavior on color { ColorAnimation { duration: 200 } }
            }

            Item { Layout.fillWidth: true }
        }

        // ── Separator ──────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 8
            Rectangle {
                anchors.centerIn: parent
                width: parent.width; height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5; color: Qt.rgba(Theme.Tokens.chalk.r,
                                                                  Theme.Tokens.chalk.g,
                                                                  Theme.Tokens.chalk.b, 0.08) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // ── Data rows ──────────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6

            FuelRow { label: "FUEL LEVEL"; value: root.fuelLevel.toFixed(1) + " L"; valueColor: Theme.Tokens.chalk }
            FuelRow { label: "FUEL / LAP"; value: root.fuelPerLap.toFixed(2) + " L"; valueColor: Theme.Tokens.chalk }
            FuelRow { label: "LAPS LEFT"; value: root.lapsLeft.toFixed(1); valueColor: root.stateColor }

            // Separator
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 6
                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width; height: 1
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 0.5; color: Qt.rgba(Theme.Tokens.chalk.r,
                                                                      Theme.Tokens.chalk.g,
                                                                      Theme.Tokens.chalk.b, 0.08) }
                        GradientStop { position: 1.0; color: "transparent" }
                    }
                }
            }

            FuelRow { label: "FUEL TO ADD"; value: root.fuelToAdd.toFixed(1) + " L"; valueColor: Theme.Tokens.pitOrange }
            FuelRow { label: "STINT"; value: root.stintLaps + " laps"; valueColor: Theme.Tokens.chalk }
            FuelRow { label: "TARGET"; value: root.targetLaps + " laps"; valueColor: Theme.Tokens.chalk }
        }
    }

    // ── Reusable data row ──────────────────────────────────────────
    component FuelRow: RowLayout {
        property string label
        property string value
        property color  valueColor: Theme.Tokens.chalk

        Layout.fillWidth: true

        Text {
            text: label
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 9
            font.weight: Font.Bold
            font.letterSpacing: 1.0
            color: Theme.Tokens.steel
        }
        Item { Layout.fillWidth: true }
        Text {
            text: value
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 13
            font.weight: Font.Bold
            color: valueColor
        }
    }
}
