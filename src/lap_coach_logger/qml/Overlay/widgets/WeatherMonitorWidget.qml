import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  WeatherMonitorWidget — track conditions display (200x160).
    Shows air/track temperature, humidity, wind, rain chance,
    and track surface state.                                        */
Rectangle {
    id: root
    width: 200
    height: 160
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real   airTemp: 0.0
    property real   trackTemp: 0.0
    property int    humidity: 0
    property real   windSpeed: 0.0
    property string windDir: "--"
    property int    rainChance: 0
    property string trackState: "DRY"       // DRY | DAMP | WET

    // ── derived ─────────────────────────────────────────────────────
    readonly property color stateColor: {
        switch (root.trackState.toUpperCase()) {
        case "WET":  return Theme.Tokens.racingPurple
        case "DAMP": return Theme.Tokens.marshalYellow
        default:     return Theme.Tokens.acidGreen
        }
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
                text: "WEATHER"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            // Track state badge
            Rectangle {
                implicitWidth: stateLabel.implicitWidth + 10
                implicitHeight: 16
                radius: 4
                color: Qt.rgba(root.stateColor.r,
                               root.stateColor.g,
                               root.stateColor.b, 0.12)
                border.width: 1
                border.color: Qt.rgba(root.stateColor.r,
                                      root.stateColor.g,
                                      root.stateColor.b, 0.25)

                Text {
                    id: stateLabel
                    anchors.centerIn: parent
                    text: root.trackState.toUpperCase()
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                    color: root.stateColor
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
            spacing: 5

            WxRow { label: "AIR TEMP"; value: root.airTemp.toFixed(1) + " C" }
            WxRow { label: "TRACK TEMP"; value: root.trackTemp.toFixed(1) + " C" }
            WxRow { label: "HUMIDITY"; value: root.humidity + "%" }
            WxRow { label: "WIND"; value: root.windSpeed.toFixed(0) + " km/h " + root.windDir }
            WxRow {
                label: "RAIN"
                value: root.rainChance + "%"
                valueColor: root.rainChance > 50 ? Theme.Tokens.racingPurple
                           : root.rainChance > 20 ? Theme.Tokens.marshalYellow
                           : Theme.Tokens.chalk
            }
        }
    }

    // ── Reusable data row ──────────────────────────────────────────
    component WxRow: RowLayout {
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
