import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  LaptimeGraphWidget — bar chart of recent lap times (320 x 180).
    Canvas-based with rounded-top bars, pitOrange glow on best lap,
    average line (horizontal dashed), axis labels (lap numbers below,
    time above best), and empty-state placeholder.                    */
GlassSurface {
    id: root
    width: 320
    implicitHeight: 180

    // ── public API ──────────────────────────────────────────────────
    property var lapTimes: []   // list of {lap: int, time_s: float}

    // ── derived ─────────────────────────────────────────────────────
    readonly property bool hasData: (root.lapTimes && root.lapTimes.length > 0)

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

        // ── Empty state ────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !root.hasData

            ColumnLayout {
                anchors.centerIn: parent
                spacing: 4

                Text {
                    text: "NO DATA"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    font.letterSpacing: 1.0
                    color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.25)
                    horizontalAlignment: Text.AlignHCenter
                    Layout.alignment: Qt.AlignHCenter
                }

                Text {
                    text: "Complete a lap to see times"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: 10
                    color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.15)
                    horizontalAlignment: Text.AlignHCenter
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }

        // ── Chart canvas ───────────────────────────────────────────
        Canvas {
            id: chartCanvas
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.hasData

            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            Component.onCompleted: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                var w = width
                var h = height
                if (w <= 0 || h <= 0) return
                ctx.reset()
                ctx.clearRect(0, 0, w, h)

                var times = root.lapTimes
                if (!times || times.length === 0) return

                // Find min / max / average times for scaling
                var minT = Infinity
                var maxT = -Infinity
                var sum = 0
                var bestIdx = 0
                for (var i = 0; i < times.length; i++) {
                    var t = times[i].time_s
                    if (t < minT) { minT = t; bestIdx = i }
                    if (t > maxT) maxT = t
                    sum += t
                }
                var avg = sum / times.length

                var range = maxT - minT
                if (range < 0.001) range = 1.0

                var barCount = times.length
                var gap = 3
                var barW = Math.max(4, (w - (barCount - 1) * gap) / barCount)
                var labelH = 18      // room for lap number labels below
                var topLabelH = 14   // room for time label above best bar
                var chartH = h - labelH - topLabelH

                // ── Baseline at bottom of chart area ───────────────
                ctx.beginPath()
                ctx.moveTo(0, topLabelH + chartH)
                ctx.lineTo(w, topLabelH + chartH)
                ctx.strokeStyle = Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08).toString()
                ctx.lineWidth = 1
                ctx.stroke()

                // ── Average line (horizontal dashed) ───────────────
                var avgPct = range > 0.001
                             ? 0.2 + 0.8 * (1.0 - (avg - minT) / range)
                             : 0.6
                var avgY = topLabelH + chartH - Math.max(4, chartH * avgPct)

                ctx.save()
                ctx.setLineDash([4, 3])
                ctx.beginPath()
                ctx.moveTo(0, avgY)
                ctx.lineTo(w, avgY)
                ctx.strokeStyle = Theme.Tokens.subtle(Theme.Tokens.chalk, 0.18).toString()
                ctx.lineWidth = 1
                ctx.stroke()
                ctx.restore()

                // "AVG" label on right of the dashed line
                ctx.fillStyle = Theme.Tokens.subtle(Theme.Tokens.chalk, 0.3).toString()
                ctx.font = "bold 7px " + Theme.Typography.monoFamily
                ctx.textAlign = "right"
                ctx.fillText("AVG", w, avgY - 3)

                // ── Draw bars ──────────────────────────────────────
                for (var j = 0; j < barCount; j++) {
                    var entry = times[j]
                    var time_s = entry.time_s
                    var lap = entry.lap !== undefined ? entry.lap : (j + 1)

                    // Normalize bar height (min = 20%, max = 100%)
                    var pct = range > 0.001
                              ? 0.2 + 0.8 * (1.0 - (time_s - minT) / range)
                              : 0.6
                    var barH = Math.max(4, chartH * pct)

                    var x = j * (barW + gap)
                    var y = topLabelH + chartH - barH

                    // Color: best = pitOrange, last = chalk, others = steel
                    var isBest = (j === bestIdx)
                    var isLast = (j === barCount - 1)
                    var barColor
                    if (isBest) {
                        barColor = Theme.Tokens.pitOrange.toString()
                    } else if (isLast) {
                        barColor = Theme.Tokens.chalk.toString()
                    } else {
                        barColor = Theme.Tokens.steel.toString()
                    }

                    // Glow behind best bar
                    if (isBest) {
                        ctx.save()
                        ctx.shadowColor = Theme.Tokens.pitOrange.toString()
                        ctx.shadowBlur = 8
                        ctx.shadowOffsetX = 0
                        ctx.shadowOffsetY = 0
                    }

                    // Draw bar with rounded top
                    var r = Math.min(3, barW / 2)
                    ctx.beginPath()
                    ctx.moveTo(x, topLabelH + chartH)
                    ctx.lineTo(x, y + r)
                    ctx.arcTo(x, y, x + r, y, r)
                    ctx.lineTo(x + barW - r, y)
                    ctx.arcTo(x + barW, y, x + barW, y + r, r)
                    ctx.lineTo(x + barW, topLabelH + chartH)
                    ctx.closePath()
                    ctx.fillStyle = barColor
                    ctx.globalAlpha = 0.85
                    ctx.fill()
                    ctx.globalAlpha = 1.0

                    if (isBest) {
                        ctx.restore()
                    }

                    // Lap number below bar
                    ctx.fillStyle = (isBest ? Theme.Tokens.pitOrange : Theme.Tokens.steel).toString()
                    ctx.font = "bold 8px " + Theme.Typography.monoFamily
                    ctx.textAlign = "center"
                    ctx.fillText("" + lap, x + barW / 2, topLabelH + chartH + 12)

                    // Time label above best bar
                    if (isBest) {
                        var mins = Math.floor(time_s / 60)
                        var secs = (time_s % 60).toFixed(1)
                        var label = (mins > 0 ? mins + ":" : "") + (secs < 10 && mins > 0 ? "0" : "") + secs
                        ctx.fillStyle = Theme.Tokens.pitOrange.toString()
                        ctx.font = "bold 8px " + Theme.Typography.monoFamily
                        ctx.textAlign = "center"
                        ctx.fillText(label, x + barW / 2, y - 3)
                    }
                }
            }
        }
    }
}
