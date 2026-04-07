import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  GForceMeterWidget — dedicated G-force visualisation (200x200).
    Canvas circle with current G dot, trail, and axis labels
    for lateral and longitudinal forces.                            */
Rectangle {
    id: root
    width: 200
    height: 200
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real latG: 0.0
    property real longG: 0.0
    property real maxG: 3.0
    property var  trail: []         // [{x, y}] recent G samples

    // ── repaint on data change ──────────────────────────────────────
    onLatGChanged:   gCanvas.requestPaint()
    onLongGChanged:  gCanvas.requestPaint()
    onTrailChanged:  gCanvas.requestPaint()

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 8
            bottomMargin: 8
            leftMargin: 8
            rightMargin: 8
        }
        spacing: 4

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "G-FORCE"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            Text {
                text: {
                    var total = Math.sqrt(root.latG * root.latG + root.longG * root.longG)
                    return total.toFixed(2) + " G"
                }
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                color: Theme.Tokens.steel
                opacity: 0.7
            }
        }

        // ── G-force canvas ─────────────────────────────────────────
        Canvas {
            id: gCanvas
            Layout.fillWidth: true
            Layout.fillHeight: true

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)

                var cx = width / 2
                var cy = height / 2
                var maxR = Math.min(cx, cy) - 8

                // ── Reference circles (1G, 2G, maxG) ──────────
                var rings = [1, 2, root.maxG]
                ctx.strokeStyle = Qt.rgba(Theme.Tokens.steel.r,
                                          Theme.Tokens.steel.g,
                                          Theme.Tokens.steel.b, 0.10)
                ctx.lineWidth = 1
                for (var i = 0; i < rings.length; i++) {
                    var r = (rings[i] / root.maxG) * maxR
                    ctx.beginPath()
                    ctx.arc(cx, cy, r, 0, 2 * Math.PI)
                    ctx.stroke()
                }

                // ── Axis lines ─────────────────────────────────
                ctx.strokeStyle = Qt.rgba(Theme.Tokens.steel.r,
                                          Theme.Tokens.steel.g,
                                          Theme.Tokens.steel.b, 0.08)
                ctx.beginPath()
                ctx.moveTo(cx, cy - maxR)
                ctx.lineTo(cx, cy + maxR)
                ctx.moveTo(cx - maxR, cy)
                ctx.lineTo(cx + maxR, cy)
                ctx.stroke()

                // ── Axis labels ────────────────────────────────
                ctx.fillStyle = Qt.rgba(Theme.Tokens.steel.r,
                                        Theme.Tokens.steel.g,
                                        Theme.Tokens.steel.b, 0.40)
                ctx.font = "7px monospace"
                ctx.textAlign = "center"
                ctx.fillText("BRAKE", cx, cy - maxR - 2)
                ctx.fillText("ACCEL", cx, cy + maxR + 8)
                ctx.textAlign = "left"
                ctx.fillText("L", cx - maxR - 8, cy + 3)
                ctx.textAlign = "right"
                ctx.fillText("R", cx + maxR + 8, cy + 3)

                // ── Trail ──────────────────────────────────────
                var trailPts = root.trail || []
                if (trailPts.length > 1) {
                    for (var t = 0; t < trailPts.length; t++) {
                        var tp = trailPts[t]
                        var tpx = cx + (tp.x / root.maxG) * maxR
                        var tpy = cy - (tp.y / root.maxG) * maxR
                        var alpha = 0.04 + (t / trailPts.length) * 0.12
                        ctx.fillStyle = Qt.rgba(Theme.Tokens.pitOrange.r,
                                                Theme.Tokens.pitOrange.g,
                                                Theme.Tokens.pitOrange.b, alpha)
                        ctx.beginPath()
                        ctx.arc(tpx, tpy, 2, 0, 2 * Math.PI)
                        ctx.fill()
                    }
                }

                // ── Current G dot ──────────────────────────────
                var gx = cx + (root.latG / root.maxG) * maxR
                var gy = cy - (root.longG / root.maxG) * maxR

                // Clamp to circle
                var dist = Math.sqrt((gx - cx) * (gx - cx) + (gy - cy) * (gy - cy))
                if (dist > maxR) {
                    gx = cx + (gx - cx) / dist * maxR
                    gy = cy + (gy - cy) / dist * maxR
                }

                // Glow
                ctx.fillStyle = Qt.rgba(Theme.Tokens.acidGreen.r,
                                        Theme.Tokens.acidGreen.g,
                                        Theme.Tokens.acidGreen.b, 0.20)
                ctx.beginPath()
                ctx.arc(gx, gy, 8, 0, 2 * Math.PI)
                ctx.fill()

                // Core dot
                ctx.fillStyle = Theme.Tokens.acidGreen.toString()
                ctx.beginPath()
                ctx.arc(gx, gy, 4, 0, 2 * Math.PI)
                ctx.fill()

                // ── 1G label ───────────────────────────────────
                ctx.fillStyle = Qt.rgba(Theme.Tokens.steel.r,
                                        Theme.Tokens.steel.g,
                                        Theme.Tokens.steel.b, 0.30)
                ctx.font = "7px monospace"
                ctx.textAlign = "left"
                var oneGR = (1 / root.maxG) * maxR
                ctx.fillText("1G", cx + oneGR + 3, cy - 2)
            }

            Component.onCompleted: requestPaint()
        }
    }
}
