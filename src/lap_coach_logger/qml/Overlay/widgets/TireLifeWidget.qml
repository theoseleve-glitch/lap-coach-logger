import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  TireLifeWidget — shows tire grip remaining, temps, and condition.
    Category: strategy. 220x180.  */
Rectangle {
    id: root
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 220; height: 180; color: "transparent"

    property real gripPct: 100.0
    property int lapCount: 0
    property int lapsRemaining: 99
    property real wearRate: 0.0
    property string condition: "good"  // good/worn/critical
    property real tempLF: 0; property real tempRF: 0
    property real tempLR: 0; property real tempRR: 0
    // T159: degraded state — tire telemetry stalled or
    // unavailable. When true the headline grip% / laps-left
    // readouts render `--` placeholders in steel, distinguishing
    // "no tire data" from "100% grip in green".
    property bool degraded: false

    readonly property color condColor: condition === "critical" ? Theme.Tokens.safetyRed
                                     : condition === "worn" ? Theme.Tokens.marshalYellow
                                     : Theme.Tokens.acidGreen

    ColumnLayout {
        anchors { fill: parent; margins: 12 }
        spacing: 8

        // Header
        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "TIRE LIFE"
                font { family: Theme.Typography.monoFamily; pixelSize: Math.round(9 * root.fontScale); weight: Font.Bold; letterSpacing: 2 }
                color: Theme.Tokens.steel
            }
            Item { Layout.fillWidth: true }
            // Condition badge
            Rectangle {
                width: condLabel.implicitWidth + 10; height: 16; radius: 4
                color: Qt.rgba(root.condColor.r, root.condColor.g, root.condColor.b, 0.15)
                border.width: 1; border.color: Qt.rgba(root.condColor.r, root.condColor.g, root.condColor.b, 0.3)
                Text {
                    id: condLabel; anchors.centerIn: parent
                    text: root.degraded ? "--" : root.condition.toUpperCase()
                    font { family: Theme.Typography.monoFamily; pixelSize: Math.round(8 * root.fontScale); weight: Font.Bold; letterSpacing: 1 }
                    color: root.degraded ? Theme.Tokens.steel : root.condColor
                }
            }
        }

        // Grip bar
        Rectangle {
            Layout.fillWidth: true; height: 8; radius: 4
            color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.06)
            Rectangle {
                width: root.degraded ? 0 : parent.width * Math.max(0, Math.min(1, root.gripPct / 100))
                height: parent.height; radius: 4
                color: root.condColor
                Behavior on width { NumberAnimation { duration: 300 } }
                Behavior on color { ColorAnimation { duration: 300 } }
            }
        }

        // Grip percentage + laps
        RowLayout {
            Layout.fillWidth: true
            Text {
                text: root.degraded ? "--" : Math.round(root.gripPct) + "%"
                font { family: Theme.Typography.monoFamily; pixelSize: Math.round(22 * root.fontScale); weight: Font.Bold }
                color: root.degraded ? Theme.Tokens.steel : root.condColor
            }
            Item { Layout.fillWidth: true }
            Column {
                spacing: 1
                Text {
                    text: root.degraded ? "-- laps left" : root.lapsRemaining + " laps left"
                    font { family: Theme.Typography.monoFamily; pixelSize: Math.round(10 * root.fontScale); weight: Font.Bold }
                    color: root.degraded ? Theme.Tokens.steel : Theme.Tokens.chalk
                    horizontalAlignment: Text.AlignRight
                }
                Text {
                    text: root.degraded ? "stint: -- laps" : "stint: " + root.lapCount + " laps"
                    font { family: Theme.Typography.monoFamily; pixelSize: Math.round(9 * root.fontScale) }
                    color: Theme.Tokens.steel; horizontalAlignment: Text.AlignRight
                }
            }
        }

        // Tire temps grid (2x2)
        Grid {
            Layout.fillWidth: true
            columns: 2; rows: 2; spacing: 4

            Repeater {
                model: [
                    { label: "LF", temp: root.tempLF },
                    { label: "RF", temp: root.tempRF },
                    { label: "LR", temp: root.tempLR },
                    { label: "RR", temp: root.tempRR }
                ]
                delegate: Rectangle {
                    required property var modelData
                    width: (parent.width - 4) / 2; height: 22; radius: 4
                    color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.03)
                    Row {
                        anchors { fill: parent; leftMargin: 6; rightMargin: 6 }
                        spacing: 4
                        Text {
                            text: modelData.label
                            font { family: Theme.Typography.monoFamily; pixelSize: Math.round(8 * root.fontScale); weight: Font.Bold }
                            color: Theme.Tokens.steel; anchors.verticalCenter: parent.verticalCenter
                        }
                        Item { width: 1 }
                        Text {
                            text: root.degraded ? "--" : (modelData.temp > 0 ? Math.round(modelData.temp) + "\u00B0" : "--")
                            font { family: Theme.Typography.monoFamily; pixelSize: Math.round(11 * root.fontScale); weight: Font.Bold }
                            color: root.degraded ? Theme.Tokens.steel : (modelData.temp > 100 ? Theme.Tokens.safetyRed : modelData.temp > 75 ? Theme.Tokens.acidGreen : Theme.Tokens.racingPurple)
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }
            }
        }
    }
}
