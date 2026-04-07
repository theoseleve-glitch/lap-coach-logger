import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  FlagsWidget — current flag status display (160 x 100).
    Large colored rectangle with the flag name. Supports
    green / yellow / red / blue / white / checkered / none.      */
Rectangle {
    id: root
    width: 160
    height: 100
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property string flag: "none"   // green|yellow|red|blue|white|checkered|none

    // ── flag color mapping ──────────────────────────────────────────
    readonly property color flagColor: {
        switch (flag) {
        case "green":     return Theme.Tokens.acidGreen
        case "yellow":    return Theme.Tokens.marshalYellow
        case "red":       return Theme.Tokens.safetyRed
        case "blue":      return "#3B82F6"
        case "white":     return Theme.Tokens.chalk
        case "checkered": return Theme.Tokens.chalk
        default:          return Theme.Tokens.steel
        }
    }

    readonly property string flagLabel: {
        switch (flag) {
        case "green":     return "GREEN"
        case "yellow":    return "YELLOW"
        case "red":       return "RED"
        case "blue":      return "BLUE"
        case "white":     return "WHITE"
        case "checkered": return "FINISH"
        default:          return "NO FLAG"
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
        Text {
            text: "FLAG"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 9
            font.weight: Font.Bold
            font.letterSpacing: 1.2
            color: Theme.Tokens.steel
        }

        Item { Layout.preferredHeight: 6 }

        // ── Flag panel ─────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 6

            color: root.flag === "none"
                   ? Qt.rgba(Theme.Tokens.steel.r,
                             Theme.Tokens.steel.g,
                             Theme.Tokens.steel.b, 0.08)
                   : Qt.rgba(root.flagColor.r,
                             root.flagColor.g,
                             root.flagColor.b, 0.20)

            border.width: 2
            border.color: root.flag === "none"
                          ? Qt.rgba(Theme.Tokens.steel.r,
                                    Theme.Tokens.steel.g,
                                    Theme.Tokens.steel.b, 0.15)
                          : Qt.rgba(root.flagColor.r,
                                    root.flagColor.g,
                                    root.flagColor.b, 0.50)

            Behavior on color { ColorAnimation { duration: 300 } }
            Behavior on border.color { ColorAnimation { duration: 300 } }

            // Checkered pattern (canvas overlay for checkered flag)
            Canvas {
                anchors.fill: parent
                visible: root.flag === "checkered"
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.reset()
                    ctx.clearRect(0, 0, width, height)
                    var sq = 10
                    ctx.globalAlpha = 0.15
                    for (var row = 0; row < height / sq; row++) {
                        for (var col = 0; col < width / sq; col++) {
                            if ((row + col) % 2 === 0) {
                                ctx.fillStyle = Theme.Tokens.chalk.toString()
                                ctx.fillRect(col * sq, row * sq, sq, sq)
                            }
                        }
                    }
                }
                Component.onCompleted: requestPaint()
            }

            // Flag label
            Text {
                anchors.centerIn: parent
                text: root.flagLabel
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 16
                font.weight: Font.Bold
                font.letterSpacing: 2
                color: root.flag === "none"
                       ? Theme.Tokens.steel
                       : root.flagColor

                Behavior on color { ColorAnimation { duration: 300 } }
            }
        }
    }
}
