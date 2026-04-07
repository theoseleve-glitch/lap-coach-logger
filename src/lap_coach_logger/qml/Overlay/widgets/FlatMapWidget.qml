import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  FlatMapWidget — horizontal flattened track strip (300x100).
    Shows the track as a linear bar with car position marker
    and sector boundary lines.                                      */
Rectangle {
    id: root
    width: 300
    height: 100
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real carPosition: 0.0      // 0-1 lap fraction
    property var  sectors: []           // [float] sector boundary positions 0-1

    // ── repaint on data change ──────────────────────────────────────
    onCarPositionChanged: flatCanvas.requestPaint()
    onSectorsChanged:     flatCanvas.requestPaint()

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 8
            bottomMargin: 8
            leftMargin: 10
            rightMargin: 10
        }
        spacing: 4

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "TRACK"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            Text {
                text: Math.round(root.carPosition * 100) + "%"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                color: Theme.Tokens.steel
                opacity: 0.7
            }
        }

        // ── Flat strip canvas ──────────────────────────────────────
        Canvas {
            id: flatCanvas
            Layout.fillWidth: true
            Layout.fillHeight: true

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)

                var pad = 4
                var barY = height * 0.35
                var barH = 10
                var barW = width - pad * 2

                // ── Track strip background ─────────────────────
                ctx.fillStyle = Qt.rgba(Theme.Tokens.chalk.r,
                                        Theme.Tokens.chalk.g,
                                        Theme.Tokens.chalk.b, 0.06)
                ctx.beginPath()
                ctx.roundedRect(pad, barY, barW, barH, 3, 3)
                ctx.fill()

                // ── Filled portion up to car position ──────────
                var fillW = Math.max(0, Math.min(1, root.carPosition)) * barW
                if (fillW > 0) {
                    ctx.fillStyle = Qt.rgba(Theme.Tokens.acidGreen.r,
                                            Theme.Tokens.acidGreen.g,
                                            Theme.Tokens.acidGreen.b, 0.25)
                    ctx.beginPath()
                    ctx.roundedRect(pad, barY, fillW, barH, 3, 3)
                    ctx.fill()
                }

                // ── Sector boundaries ──────────────────────────
                var sectorList = root.sectors || []
                ctx.strokeStyle = Qt.rgba(Theme.Tokens.steel.r,
                                          Theme.Tokens.steel.g,
                                          Theme.Tokens.steel.b, 0.30)
                ctx.lineWidth = 1
                for (var i = 0; i < sectorList.length; i++) {
                    var sx = pad + sectorList[i] * barW
                    ctx.beginPath()
                    ctx.moveTo(sx, barY - 4)
                    ctx.lineTo(sx, barY + barH + 4)
                    ctx.stroke()

                    // Sector label
                    ctx.fillStyle = Qt.rgba(Theme.Tokens.steel.r,
                                            Theme.Tokens.steel.g,
                                            Theme.Tokens.steel.b, 0.50)
                    ctx.font = "7px monospace"
                    ctx.textAlign = "center"
                    ctx.fillText("S" + (i + 1), sx, barY + barH + 14)
                }

                // ── Start/finish markers ───────────────────────
                ctx.fillStyle = Theme.Tokens.chalk.toString()
                ctx.font = "7px monospace"
                ctx.textAlign = "left"
                ctx.fillText("S/F", pad, barY - 6)

                // ── Car position marker (triangle) ─────────────
                var cx = pad + root.carPosition * barW
                var triY = barY - 2
                ctx.fillStyle = Theme.Tokens.acidGreen.toString()
                ctx.beginPath()
                ctx.moveTo(cx, triY)
                ctx.lineTo(cx - 4, triY - 6)
                ctx.lineTo(cx + 4, triY - 6)
                ctx.closePath()
                ctx.fill()
            }

            Component.onCompleted: requestPaint()
        }
    }
}
