import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  LaptimeGraphWidget — bar chart of recent lap times (320 x 180).
    Canvas-based. Bars colored: best = pitOrange, current = chalk,
    slow = steel.                                                    */
Rectangle {
    id: root
    width: 320
    height: 180
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property var lapTimes: []   // list of {lap: int, time_s: float}

    onLapTimesChanged: chartCanvas.requestPaint()

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 14
            rightMargin: 14
        }
        spacing: 6

        // ── Header ─────────────────────────────────────────────────
        Text {
            text: "LAP TIMES"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 9
            font.weight: Font.Bold
            font.letterSpacing: 1.2
            color: Theme.Tokens.steel
        }

        // ── Chart canvas ───────────────────────────────────────────
        Canvas {
            id: chartCanvas
            Layout.fillWidth: true
            Layout.fillHeight: true

            Component.onCompleted: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                var w = width
                var h = height
                ctx.reset()
                ctx.clearRect(0, 0, w, h)

                var times = root.lapTimes
                if (!times || times.length === 0) return

                // Find min / max times for scaling
                var minT = Infinity
                var maxT = -Infinity
                for (var i = 0; i < times.length; i++) {
                    var t = times[i].time_s
                    if (t < minT) minT = t
                    if (t > maxT) maxT = t
                }

                var range = maxT - minT
                if (range < 0.001) range = 1.0

                var barCount = times.length
                var gap = 3
                var barW = Math.max(4, (w - (barCount - 1) * gap) / barCount)
                var chartH = h - 18   // leave room for lap numbers

                // Baseline at bottom of chart area
                ctx.beginPath()
                ctx.moveTo(0, chartH)
                ctx.lineTo(w, chartH)
                ctx.strokeStyle = Qt.rgba(Theme.Tokens.chalk.r,
                                          Theme.Tokens.chalk.g,
                                          Theme.Tokens.chalk.b, 0.08)
                ctx.lineWidth = 1
                ctx.stroke()

                for (var j = 0; j < barCount; j++) {
                    var entry = times[j]
                    var time_s = entry.time_s
                    var lap = entry.lap

                    // Normalize bar height (min = 20%, max = 100%)
                    var pct = range > 0.001
                              ? 0.2 + 0.8 * (1.0 - (time_s - minT) / range)
                              : 0.6
                    var barH = Math.max(4, chartH * pct)

                    var x = j * (barW + gap)
                    var y = chartH - barH

                    // Color: best = pitOrange, last = chalk, others = steel
                    var barColor
                    if (time_s <= minT + 0.001) {
                        barColor = Theme.Tokens.pitOrange.toString()
                    } else if (j === barCount - 1) {
                        barColor = Theme.Tokens.chalk.toString()
                    } else {
                        barColor = Theme.Tokens.steel.toString()
                    }

                    // Draw bar with rounded top
                    var r = Math.min(3, barW / 2)
                    ctx.beginPath()
                    ctx.moveTo(x, chartH)
                    ctx.lineTo(x, y + r)
                    ctx.arcTo(x, y, x + r, y, r)
                    ctx.lineTo(x + barW - r, y)
                    ctx.arcTo(x + barW, y, x + barW, y + r, r)
                    ctx.lineTo(x + barW, chartH)
                    ctx.closePath()
                    ctx.fillStyle = barColor
                    ctx.globalAlpha = 0.85
                    ctx.fill()
                    ctx.globalAlpha = 1.0

                    // Lap number below bar
                    ctx.fillStyle = Theme.Tokens.steel.toString()
                    ctx.font = "bold 8px " + Theme.Typography.monoFamily
                    ctx.textAlign = "center"
                    ctx.fillText("" + lap, x + barW / 2, chartH + 12)
                }
            }
        }
    }
}
