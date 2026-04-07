import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  WeatherMonitorWidget -- track conditions display (200x180).
    Shows air/track temperature, humidity, wind with compass arrow,
    rain chance as mini progress bar, and track surface state badge
    with glow: DRY=green, DAMP=yellow, WET=blue.                    */
Rectangle {
    id: root
    width: 200
    height: 180
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real   airTemp: 0.0
    property real   trackTemp: 0.0
    property int    humidity: 0
    property real   windSpeed: 0.0
    property string windDir: "--"
    property int    rainChance: 0
    property string trackState: "DRY"       // DRY | DAMP | WET

    // ── null-safe helpers ───────────────────────────────────────────
    function safeFix(v, d) { return isFinite(v) ? v.toFixed(d) : "--" }
    function safeInt(v)    { return isFinite(v) ? Math.max(0, Math.round(v)) : 0 }
    readonly property string safeState: (typeof trackState === "string" && trackState.length > 0)
                                         ? trackState.toUpperCase() : "DRY"
    readonly property string safeWindDir: (typeof windDir === "string" && windDir.length > 0)
                                           ? windDir : "--"
    readonly property int    safeRain: isFinite(rainChance) ? Math.max(0, Math.min(100, rainChance)) : 0

    // ── temperature color (cold=blue, normal=green, hot=red) ────────
    function tempColor(t) {
        if (!isFinite(t)) return Theme.Tokens.chalk
        if (t < 10)  return Theme.Tokens.racingPurple   // cold
        if (t < 35)  return Theme.Tokens.acidGreen       // normal
        return Theme.Tokens.safetyRed                     // hot
    }

    // ── track state badge color with glow ───────────────────────────
    readonly property color stateColor: {
        switch (safeState) {
        case "WET":  return Theme.Tokens.racingPurple
        case "DAMP": return Theme.Tokens.marshalYellow
        default:     return Theme.Tokens.acidGreen
        }
    }

    // ── rain color ──────────────────────────────────────────────────
    readonly property color rainColor: {
        if (safeRain > 50) return Theme.Tokens.racingPurple
        if (safeRain > 20) return Theme.Tokens.marshalYellow
        return Theme.Tokens.chalk
    }

    // ── wind direction to rotation ──────────────────────────────────
    function windRotation(dir) {
        var map = { "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
                    "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
                    "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
                    "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5 }
        return (typeof dir === "string") ? (map[dir.toUpperCase()] || -1) : -1
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
                text: "WEATHER"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Theme.Typography.microWeight
                font.letterSpacing: Theme.Typography.microSpacing
                color: Theme.Tokens.steel
            }

            // Track state badge with glow
            Rectangle {
                id: stateBadge
                implicitWidth: stateLabel.implicitWidth + 12
                implicitHeight: 16
                radius: 4
                color: Theme.Tokens.subtle(root.stateColor, 0.12)
                border.width: 1
                border.color: Theme.Tokens.subtle(root.stateColor, 0.25)

                Behavior on color        { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                Behavior on border.color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }

                // Glow pulse for non-DRY states
                property real glowOpacity: 0
                SequentialAnimation on glowOpacity {
                    running: root.safeState !== "DRY"
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.30; duration: Theme.Motion.recordingPulseDuration; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.08; duration: Theme.Motion.recordingPulseDuration; easing.type: Easing.InOutSine }
                }

                Rectangle {
                    anchors.fill: parent
                    radius: parent.radius
                    color: root.stateColor
                    opacity: root.safeState !== "DRY" ? stateBadge.glowOpacity : 0
                    visible: root.safeState !== "DRY"
                }

                Text {
                    id: stateLabel
                    anchors.centerIn: parent
                    text: root.safeState
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
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
            spacing: 5

            DataRow {
                label: "AIR TEMP"
                value: root.safeFix(root.airTemp, 1) + " \u00B0C"
                valueColor: root.tempColor(root.airTemp)
            }
            DataRow {
                label: "TRACK TEMP"
                value: root.safeFix(root.trackTemp, 1) + " \u00B0C"
                valueColor: root.tempColor(root.trackTemp)
            }
            DataRow {
                label: "HUMIDITY"
                value: root.safeInt(root.humidity) + "%"
            }

            // ── Wind with compass arrow ────────────────────────────
            RowLayout {
                Layout.fillWidth: true

                Text {
                    text: "WIND"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Theme.Typography.microSize
                    font.weight: Theme.Typography.microWeight
                    font.letterSpacing: 1.0
                    color: Theme.Tokens.steel
                }
                Item { Layout.fillWidth: true }

                // Compass arrow
                Text {
                    id: windArrow
                    text: "\u25B2"
                    font.pixelSize: 10
                    color: Theme.Tokens.chalk
                    visible: root.windRotation(root.safeWindDir) >= 0
                    rotation: root.windRotation(root.safeWindDir)
                    Behavior on rotation { NumberAnimation { duration: 300 } }
                }

                Text {
                    text: root.safeFix(root.windSpeed, 0) + " km/h " + root.safeWindDir
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 13
                    font.weight: Font.Bold
                    color: Theme.Tokens.chalk
                }
            }

            // ── Rain chance with mini progress bar ─────────────────
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                RowLayout {
                    Layout.fillWidth: true

                    Text {
                        text: "RAIN"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Theme.Typography.microWeight
                        font.letterSpacing: 1.0
                        color: Theme.Tokens.steel
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: root.safeRain + "%"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 13
                        font.weight: Font.Bold
                        color: root.rainColor
                        Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                    }
                }

                // Mini progress bar
                Rectangle {
                    Layout.fillWidth: true
                    height: 3
                    radius: 1.5
                    color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                    Rectangle {
                        width: parent.width * (root.safeRain / 100)
                        height: parent.height
                        radius: parent.radius
                        color: root.rainColor
                        Behavior on width { NumberAnimation { duration: 300 } }
                        Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                    }
                }
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
            font.pixelSize: 13
            font.weight: Font.Bold
            color: valueColor
            Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
        }
    }
}
