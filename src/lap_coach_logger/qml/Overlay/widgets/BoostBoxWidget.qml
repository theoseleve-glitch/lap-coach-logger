import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  BoostBoxWidget — ERS/KERS boost level indicator (160x100).
    Arc gauge showing available boost energy with mode badge.        */
Rectangle {
    id: root
    width: 160
    height: 100
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real   boostLevel: 0.0     // 0-1
    property string boostMode: "off"    // "deploy" | "harvest" | "off"
    property real   maxBoost: 1.0

    // ── derived ─────────────────────────────────────────────────────
    readonly property color modeColor: {
        switch (root.boostMode.toLowerCase()) {
        case "deploy":  return Theme.Tokens.acidGreen
        case "harvest": return Theme.Tokens.racingPurple
        default:        return Theme.Tokens.steel
        }
    }

    // ── repaint on change ───────────────────────────────────────────
    onBoostLevelChanged: boostCanvas.requestPaint()
    onBoostModeChanged:  boostCanvas.requestPaint()

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 8
            bottomMargin: 6
            leftMargin: 10
            rightMargin: 10
        }
        spacing: 2

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "BOOST"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            // Mode badge
            Rectangle {
                implicitWidth: modeLabel.implicitWidth + 10
                implicitHeight: 14
                radius: 3
                color: Qt.rgba(root.modeColor.r,
                               root.modeColor.g,
                               root.modeColor.b, 0.12)
                border.width: 1
                border.color: Qt.rgba(root.modeColor.r,
                                      root.modeColor.g,
                                      root.modeColor.b, 0.25)

                Text {
                    id: modeLabel
                    anchors.centerIn: parent
                    text: root.boostMode.toUpperCase()
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                    color: root.modeColor
                }
            }

            Item { Layout.fillWidth: true }
        }

        // ── Arc gauge ──────────────────────────────────────────────
        Canvas {
            id: boostCanvas
            Layout.fillWidth: true
            Layout.fillHeight: true

            property real animatedLevel: root.boostLevel
            Behavior on animatedLevel { NumberAnimation { duration: 200 } }
            onAnimatedLevelChanged: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)

                var cx = width / 2
                var cy = height * 0.65
                var r = Math.min(cx, height * 0.55) - 4
                var lineWidth = 5
                var startAngle = Math.PI * 0.8
                var endAngle = Math.PI * 2.2
                var totalAngle = endAngle - startAngle

                // Background arc
                ctx.beginPath()
                ctx.arc(cx, cy, r, startAngle, endAngle)
                ctx.strokeStyle = Qt.rgba(Theme.Tokens.chalk.r,
                                          Theme.Tokens.chalk.g,
                                          Theme.Tokens.chalk.b, 0.06)
                ctx.lineWidth = lineWidth
                ctx.lineCap = "round"
                ctx.stroke()

                // Filled arc
                var pct = Math.max(0, Math.min(1, animatedLevel / root.maxBoost))
                if (pct > 0) {
                    ctx.beginPath()
                    ctx.arc(cx, cy, r, startAngle, startAngle + totalAngle * pct)
                    ctx.strokeStyle = root.modeColor.toString()
                    ctx.lineWidth = lineWidth
                    ctx.lineCap = "round"
                    ctx.stroke()
                }

                // Center percentage text
                ctx.fillStyle = root.modeColor.toString()
                ctx.font = "bold 16px monospace"
                ctx.textAlign = "center"
                ctx.textBaseline = "middle"
                ctx.fillText(Math.round(pct * 100) + "%", cx, cy - 2)
            }

            Component.onCompleted: requestPaint()
        }
    }
}
