import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  FlatMapWidget -- horizontal flattened track strip (300x100).
    Shows the track as a linear bar with car position marker,
    sector boundary lines, and start/finish flag.                    */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 300
    height: 100
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real carPosition: 0.0      // 0-1 lap fraction
    property var  sectors: []           // [float] sector boundary positions 0-1

    // ── null-safe helpers ───────────────────────────────────────────
    readonly property real safePos: isFinite(carPosition) ? Math.max(0, Math.min(1, carPosition)) : 0
    readonly property var  safeSectors: Array.isArray(sectors) ? sectors : []

    // ── animated car position ───────────────────────────────────────
    property real animatedPos: safePos
    Behavior on animatedPos { NumberAnimation { duration: 150 } }
    onSafePosChanged: animatedPos = safePos

    // ── repaint on data + resize ────────────────────────────────────
    onAnimatedPosChanged: flatCanvas.requestPaint()
    onSafeSectorsChanged: flatCanvas.requestPaint()

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: Theme.Tokens.sm
            bottomMargin: Theme.Tokens.sm
            leftMargin: Theme.Tokens.md
            rightMargin: Theme.Tokens.md
        }
        spacing: Theme.Tokens.xs

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "TRACK"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Theme.Typography.microWeight
                font.letterSpacing: Theme.Typography.microSpacing
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            Text {
                text: Math.round(root.safePos * 100) + "%"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                color: Theme.Tokens.steel
                opacity: 0.7
            }
        }

        // ── Flat strip canvas ──────────────────────────────────────
        Canvas {
            id: flatCanvas
            Layout.fillWidth: true
            Layout.fillHeight: true

            onWidthChanged:  requestPaint()
            onHeightChanged: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)

                var pad = 4
                var barY = height * 0.35
                var barH = 10
                var barW = width - pad * 2

                // ── Track strip background ─────────────────────
                ctx.fillStyle = Theme.Tokens.subtle(Theme.Tokens.chalk)
                ctx.beginPath()
                ctx.roundedRect(pad, barY, barW, barH, 3, 3)
                ctx.fill()

                // ── Filled portion up to car position ──────────
                var fillW = root.animatedPos * barW
                if (fillW > 0) {
                    ctx.fillStyle = Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.20)
                    ctx.beginPath()
                    ctx.roundedRect(pad, barY, fillW, barH, 3, 3)
                    ctx.fill()
                }

                // ── Sector boundaries ──────────────────────────
                var sectorList = root.safeSectors
                ctx.strokeStyle = Theme.Tokens.subtle(Theme.Tokens.steel, 0.30)
                ctx.lineWidth = 1
                for (var i = 0; i < sectorList.length; i++) {
                    var sv = Number(sectorList[i])
                    if (!isFinite(sv)) continue
                    var sx = pad + sv * barW
                    ctx.beginPath()
                    ctx.moveTo(sx, barY - 4)
                    ctx.lineTo(sx, barY + barH + 4)
                    ctx.stroke()

                    // Sector label
                    ctx.fillStyle = Theme.Tokens.subtle(Theme.Tokens.steel, 0.50)
                    ctx.font = "7px monospace"
                    ctx.textAlign = "center"
                    ctx.fillText("S" + (i + 1), sx, barY + barH + 14)
                }

                // ── Start/finish flag marker ───────────────────
                var sfX = pad
                var sfY = barY - 10
                var sfW = 12
                var sfH = 8
                var cellW = sfW / 4
                var cellH = sfH / 2
                for (var row = 0; row < 2; row++) {
                    for (var col = 0; col < 4; col++) {
                        ctx.fillStyle = ((row + col) % 2 === 0)
                            ? Theme.Tokens.chalk.toString()
                            : Theme.Tokens.subtle(Theme.Tokens.chalk, 0.15)
                        ctx.fillRect(sfX + col * cellW, sfY + row * cellH,
                                     cellW, cellH)
                    }
                }
                // Flagpole
                ctx.strokeStyle = Theme.Tokens.subtle(Theme.Tokens.chalk, 0.40)
                ctx.lineWidth = 1
                ctx.beginPath()
                ctx.moveTo(sfX, sfY)
                ctx.lineTo(sfX, barY + barH + 4)
                ctx.stroke()

                // ── Car position marker (triangle) + glow ──────
                var cx = pad + root.animatedPos * barW
                var triY = barY - 2

                // Glow
                ctx.fillStyle = Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.25)
                ctx.beginPath()
                ctx.arc(cx, triY - 3, 8, 0, 2 * Math.PI)
                ctx.fill()

                // Triangle
                ctx.fillStyle = Theme.Tokens.pitOrange.toString()
                ctx.beginPath()
                ctx.moveTo(cx, triY)
                ctx.lineTo(cx - 5, triY - 8)
                ctx.lineTo(cx + 5, triY - 8)
                ctx.closePath()
                ctx.fill()
            }

            Component.onCompleted: requestPaint()
        }
    }
}
