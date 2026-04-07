import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  HeartRateWidget — heart rate display with BPM, pulse line, and zone (180x100).
    Shows BPM number, a Canvas sparkline of recent heart rate history,
    and a zone indicator (rest/warm/cardio/max).                              */
Rectangle {
    id: root
    width: 180
    height: 100
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property int    bpm: 0
    property string zone: "rest"    // rest | warm | cardio | max
    property var    history: []     // list of ints for sparkline

    onBpmChanged:     pulseCanvas.requestPaint()
    onHistoryChanged: pulseCanvas.requestPaint()

    // ── zone color mapping ──────────────────────────────────────────
    readonly property color zoneColor: {
        switch (root.zone) {
        case "max":    return Theme.Tokens.safetyRed
        case "cardio": return Theme.Tokens.pitOrange
        case "warm":   return Theme.Tokens.marshalYellow
        default:       return Theme.Tokens.acidGreen
        }
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 8
            bottomMargin: 8
            leftMargin: 10
            rightMargin: 10
        }
        spacing: 4

        // ── Header row ─────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "HR"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            // Zone badge
            Rectangle {
                implicitWidth: zoneLbl.implicitWidth + 8
                implicitHeight: 14
                radius: 3
                color: Qt.rgba(root.zoneColor.r,
                               root.zoneColor.g,
                               root.zoneColor.b, 0.12)
                border.width: 1
                border.color: Qt.rgba(root.zoneColor.r,
                                      root.zoneColor.g,
                                      root.zoneColor.b, 0.25)

                Text {
                    id: zoneLbl
                    anchors.centerIn: parent
                    text: root.zone.toUpperCase()
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    font.weight: Font.Bold
                    color: root.zoneColor
                }
            }

            Item { Layout.fillWidth: true }

            // BPM hero number
            Text {
                text: root.bpm > 0 ? root.bpm : "--"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 22
                font.weight: Font.Bold
                color: root.zoneColor
            }

            Text {
                text: "BPM"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight: Font.Bold
                color: Theme.Tokens.steel
                Layout.alignment: Qt.AlignBottom
                Layout.bottomMargin: 2
            }
        }

        // ── Pulse sparkline canvas ─────────────────────────────────
        Canvas {
            id: pulseCanvas
            Layout.fillWidth: true
            Layout.fillHeight: true

            Component.onCompleted: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                var w = width
                var h = height
                ctx.reset()
                ctx.clearRect(0, 0, w, h)

                var pts = root.history || []
                if (pts.length < 2) return

                // Find min/max for vertical scaling
                var mn = pts[0], mx = pts[0]
                for (var i = 1; i < pts.length; i++) {
                    if (pts[i] < mn) mn = pts[i]
                    if (pts[i] > mx) mx = pts[i]
                }
                var range = mx - mn
                if (range < 5) range = 5  // minimum range

                var pad = 4
                var drawW = w - pad * 2
                var drawH = h - pad * 2

                // Gradient fill under the line
                ctx.beginPath()
                for (var j = 0; j < pts.length; j++) {
                    var px = pad + (j / (pts.length - 1)) * drawW
                    var py = pad + drawH - ((pts[j] - mn) / range) * drawH
                    if (j === 0) ctx.moveTo(px, py)
                    else ctx.lineTo(px, py)
                }
                // Close path along the bottom
                ctx.lineTo(pad + drawW, pad + drawH)
                ctx.lineTo(pad, pad + drawH)
                ctx.closePath()
                ctx.fillStyle = Qt.rgba(root.zoneColor.r,
                                        root.zoneColor.g,
                                        root.zoneColor.b, 0.08)
                ctx.fill()

                // Stroke the line
                ctx.beginPath()
                for (var k = 0; k < pts.length; k++) {
                    var lx = pad + (k / (pts.length - 1)) * drawW
                    var ly = pad + drawH - ((pts[k] - mn) / range) * drawH
                    if (k === 0) ctx.moveTo(lx, ly)
                    else ctx.lineTo(lx, ly)
                }
                ctx.strokeStyle = root.zoneColor.toString()
                ctx.lineWidth = 1.5
                ctx.lineJoin = "round"
                ctx.stroke()

                // Latest point dot
                if (pts.length > 0) {
                    var lastIdx = pts.length - 1
                    var dx = pad + (lastIdx / (pts.length - 1)) * drawW
                    var dy = pad + drawH - ((pts[lastIdx] - mn) / range) * drawH

                    ctx.beginPath()
                    ctx.arc(dx, dy, 3, 0, Math.PI * 2)
                    ctx.fillStyle = root.zoneColor.toString()
                    ctx.fill()
                }
            }
        }
    }
}
