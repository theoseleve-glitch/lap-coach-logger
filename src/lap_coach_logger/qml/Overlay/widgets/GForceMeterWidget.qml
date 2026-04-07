import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  GForceMeterWidget — full G-force visualisation (200x200).
    Canvas circle with 1G/2G/maxG reference rings, axis labels,
    trail with fade, current G dot with racingPurple glow,
    combined-G readout, and peak-G indicator.                       */
Rectangle {
    id: root
    width: 200
    height: 200
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real latG:  0.0
    property real longG: 0.0
    property real maxG:  3.0
    property var  trail: []          // [{x, y}] recent G samples

    // ── null-safe derived ───────────────────────────────────────────
    readonly property real safeLatG:  isFinite(latG)  ? latG  : 0.0
    readonly property real safeLongG: isFinite(longG) ? longG : 0.0
    readonly property real safeMaxG:  isFinite(maxG) && maxG > 0 ? maxG : 3.0
    readonly property var  safeTrail: Array.isArray(trail) ? trail : []

    readonly property real combinedG:
        Math.sqrt(safeLatG * safeLatG + safeLongG * safeLongG)

    // ── peak tracking ───────────────────────────────────────────────
    property real peakG: 0.0
    onCombinedGChanged: if (combinedG > peakG) peakG = combinedG

    // ── repaint on data change + resize ─────────────────────────────
    onSafeLatGChanged:  gCanvas.requestPaint()
    onSafeLongGChanged: gCanvas.requestPaint()
    onSafeTrailChanged: gCanvas.requestPaint()

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: Theme.Tokens.sm
            bottomMargin: Theme.Tokens.sm
            leftMargin: Theme.Tokens.sm
            rightMargin: Theme.Tokens.sm
        }
        spacing: Theme.Tokens.xs

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.Tokens.sm

            Text {
                text: "G-FORCE"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Theme.Typography.microWeight
                font.letterSpacing: Theme.Typography.microSpacing
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            // Combined G readout
            Text {
                text: root.combinedG.toFixed(2) + " G"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                color: Theme.Tokens.steel
                opacity: 0.7
            }
        }

        // ── G-force canvas ─────────────────────────────────────────
        Canvas {
            id: gCanvas
            Layout.fillWidth: true
            Layout.fillHeight: true

            // repaint on resize
            onWidthChanged:  requestPaint()
            onHeightChanged: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)

                var cx   = width / 2
                var cy   = height / 2
                var maxR = Math.min(cx, cy) - 8
                if (maxR <= 0) return

                var steelR = Theme.Tokens.steel.r
                var steelG = Theme.Tokens.steel.g
                var steelB = Theme.Tokens.steel.b
                var labelFont = Theme.Typography.microSize + "px "
                              + Theme.Typography.monoFamily

                // ── Reference circles (1G, 2G, maxG) ──────────
                var rings = [1, 2, root.safeMaxG]
                ctx.strokeStyle = Qt.rgba(steelR, steelG, steelB, 0.10)
                ctx.lineWidth = 1
                for (var i = 0; i < rings.length; i++) {
                    var r = (rings[i] / root.safeMaxG) * maxR
                    ctx.beginPath()
                    ctx.arc(cx, cy, r, 0, 2 * Math.PI)
                    ctx.stroke()
                }

                // ── Axis lines ─────────────────────────────────
                ctx.strokeStyle = Qt.rgba(steelR, steelG, steelB, 0.08)
                ctx.beginPath()
                ctx.moveTo(cx, cy - maxR)
                ctx.lineTo(cx, cy + maxR)
                ctx.moveTo(cx - maxR, cy)
                ctx.lineTo(cx + maxR, cy)
                ctx.stroke()

                // ── Axis labels ────────────────────────────────
                ctx.fillStyle = Qt.rgba(steelR, steelG, steelB, 0.40)
                ctx.font = labelFont
                ctx.textAlign = "center"
                ctx.fillText("BRAKE", cx, cy - maxR - 2)
                ctx.fillText("ACCEL", cx, cy + maxR + 8)
                ctx.textAlign = "left"
                ctx.fillText("L", cx - maxR - 8, cy + 3)
                ctx.textAlign = "right"
                ctx.fillText("R", cx + maxR + 8, cy + 3)

                // ── 1G label ───────────────────────────────────
                ctx.fillStyle = Qt.rgba(steelR, steelG, steelB, 0.30)
                ctx.font = labelFont
                ctx.textAlign = "left"
                var oneGR = (1 / root.safeMaxG) * maxR
                ctx.fillText("1G", cx + oneGR + 3, cy - 2)

                // ── Trail with fade ────────────────────────────
                var pts = root.safeTrail
                var len = pts.length
                if (len > 1) {
                    var oR = Theme.Tokens.pitOrange.r
                    var oG = Theme.Tokens.pitOrange.g
                    var oB = Theme.Tokens.pitOrange.b
                    for (var t = 0; t < len; t++) {
                        var tp = pts[t]
                        if (!tp || !isFinite(tp.x) || !isFinite(tp.y))
                            continue
                        var tpx = cx + (tp.x / root.safeMaxG) * maxR
                        var tpy = cy - (tp.y / root.safeMaxG) * maxR
                        // older = more transparent
                        var alpha = 0.04 + (t / len) * 0.12
                        ctx.fillStyle = Qt.rgba(oR, oG, oB, alpha)
                        ctx.beginPath()
                        ctx.arc(tpx, tpy, 2, 0, 2 * Math.PI)
                        ctx.fill()
                    }
                }

                // ── Current G dot ──────────────────────────────
                var gx = cx + (root.safeLatG  / root.safeMaxG) * maxR
                var gy = cy - (root.safeLongG / root.safeMaxG) * maxR

                // Clamp to circle
                var dist = Math.sqrt((gx - cx) * (gx - cx)
                                   + (gy - cy) * (gy - cy))
                if (dist > maxR) {
                    gx = cx + (gx - cx) / dist * maxR
                    gy = cy + (gy - cy) / dist * maxR
                }

                // racingPurple glow
                var pR = Theme.Tokens.racingPurple.r
                var pG = Theme.Tokens.racingPurple.g
                var pB = Theme.Tokens.racingPurple.b
                ctx.fillStyle = Qt.rgba(pR, pG, pB, 0.20)
                ctx.beginPath()
                ctx.arc(gx, gy, 8, 0, 2 * Math.PI)
                ctx.fill()

                // Core dot
                ctx.fillStyle = Theme.Tokens.racingPurple.toString()
                ctx.beginPath()
                ctx.arc(gx, gy, 4, 0, 2 * Math.PI)
                ctx.fill()

                // ── Peak G indicator ───────────────────────────
                if (root.peakG > 0.1) {
                    ctx.fillStyle = Qt.rgba(steelR, steelG, steelB, 0.50)
                    ctx.font = labelFont
                    ctx.textAlign = "right"
                    ctx.fillText("PEAK " + root.peakG.toFixed(1) + "G",
                                 cx + maxR, cy + maxR + 8)
                }
            }

            Component.onCompleted: requestPaint()
        }
    }
}
