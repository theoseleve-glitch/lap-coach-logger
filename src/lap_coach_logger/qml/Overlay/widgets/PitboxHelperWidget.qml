import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  PitboxHelperWidget — pit stop planning display (240x160).
    Shows estimated pit entry lap, fuel to add, tire change
    recommendation, and pit time estimate.                          */
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

    // ── derived ─────────────────────────────────────────────────────
    readonly property color windowColor: root.pitWindowOpen
                                         ? Theme.Tokens.acidGreen
                                         : Theme.Tokens.steel

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
                text: "PITBOX"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            // Pit window badge
            Rectangle {
                implicitWidth: windowLabel.implicitWidth + 10
                implicitHeight: 16
                radius: 4
                color: Qt.rgba(root.windowColor.r,
                               root.windowColor.g,
                               root.windowColor.b, 0.12)
                border.width: 1
                border.color: Qt.rgba(root.windowColor.r,
                                      root.windowColor.g,
                                      root.windowColor.b, 0.25)

                Text {
                    id: windowLabel
                    anchors.centerIn: parent
                    text: root.pitWindowOpen ? "OPEN" : "CLOSED"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                    color: root.windowColor
                }
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

            PitRow { label: "PIT LAP"; value: root.pitLap > 0 ? "L" + root.pitLap : "--" }
            PitRow { label: "FUEL ADD"; value: root.fuelToAdd.toFixed(1) + " L"; valueColor: Theme.Tokens.pitOrange }
            PitRow { label: "TYRES"; value: root.tireChange ? "CHANGE" : "KEEP"; valueColor: root.tireChange ? Theme.Tokens.marshalYellow : Theme.Tokens.acidGreen }
            PitRow { label: "PIT TIME"; value: root.estimatedPitTime }
        }
    }

    // ── Reusable data row ──────────────────────────────────────────
    component PitRow: RowLayout {
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
