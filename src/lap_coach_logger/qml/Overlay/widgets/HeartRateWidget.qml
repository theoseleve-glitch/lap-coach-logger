import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  HeartRateWidget — heart rate display with BPM, sparkline, zone (180 x 100).
    Shows BPM number in large mono, a Canvas sparkline of recent HR history,
    and a zone indicator badge (rest/warm/cardio/max).

    Features: pulsing BPM animation (faster pulse = higher BPM),
    null-safe history, Canvas repaint on resize + data change.               */
Rectangle {
    id: root
    width: 180
    height: 100
    color: "transparent"

    // ── Public API ──────────────────────────────────────────────────
    property int    bpm: 0
    property string zone: "rest"    // rest | warm | cardio | max
    property var    history: []     // list of ints for sparkline

    // ── Repaint triggers ────────────────────────────────────────────
    onBpmChanged:     pulseCanvas.requestPaint()
    onHistoryChanged: pulseCanvas.requestPaint()

    // ── Zone color mapping ──────────────────────────────────────────
    readonly property color zoneColor: {
        switch (root.zone) {
        case "max":    return Theme.Tokens.safetyRed
        case "cardio": return Theme.Tokens.pitOrange
        case "warm":   return Theme.Tokens.marshalYellow
        default:       return Theme.Tokens.acidGreen
        }
    }

    // ── Null-safe helpers ───────────────────────────────────────────
    readonly property var safeHistory: Array.isArray(root.history) ? root.history : []

    // ── Pulsing animation — interval derived from BPM ───────────────
    // 60 BPM => 1000ms interval, 180 BPM => 333ms interval
    readonly property int pulseInterval: root.bpm > 0 ? Math.round(60000 / root.bpm) : 1000

    SequentialAnimation {
        id: pulseAnim
        running: root.bpm > 0
        loops: Animation.Infinite

        NumberAnimation {
            target: bpmText
            property: "scale"
            from: 1.0; to: 1.08
            duration: Math.max(80, root.pulseInterval * 0.15)
            easing.type: Easing.OutQuad
        }
        NumberAnimation {
            target: bpmText
            property: "scale"
            from: 1.08; to: 1.0
            duration: Math.max(120, root.pulseInterval * 0.35)
            easing.type: Easing.InQuad
        }
        PauseAnimation {
            duration: Math.max(100, root.pulseInterval * 0.5)
        }
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: Theme.Tokens.sm
            bottomMargin: Theme.Tokens.sm
            leftMargin: Theme.Tokens.sm + 2
            rightMargin: Theme.Tokens.sm + 2
        }
        spacing: Theme.Tokens.xs

        // ── Header row ─────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.Tokens.sm - 2

            Text {
                text: "HR"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize - 1
                font.weight: Theme.Typography.microWeight
                font.letterSpacing: Theme.Typography.microSpacing - 0.3
                color: Theme.Tokens.steel
            }

            // Zone badge
            Rectangle {
                implicitWidth: zoneLbl.implicitWidth + Theme.Tokens.sm
                implicitHeight: 14
                radius: 3
                color: Theme.Tokens.subtle(root.zoneColor, 0.12)
                border.width: 1
                border.color: Theme.Tokens.subtle(root.zoneColor, 0.25)

                Behavior on color        { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                Behavior on border.color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }

                Text {
                    id: zoneLbl
                    anchors.centerIn: parent
                    text: (root.zone || "rest").toUpperCase()
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    font.weight: Font.Bold
                    color: root.zoneColor
                    Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                }
            }

            Item { Layout.fillWidth: true }

            // BPM hero number (pulsing)
            Text {
                id: bpmText
                text: root.bpm > 0 ? root.bpm : "--"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 22
                font.weight: Font.Bold
                color: root.zoneColor
                transformOrigin: Item.Center
                Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
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
            onWidthChanged:  requestPaint()
            onHeightChanged: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                var w = width
                var h = height
                if (w <= 0 || h <= 0) return
                ctx.reset()
                ctx.clearRect(0, 0, w, h)

                var pts = root.safeHistory
                if (pts.length < 2) return

                // Find min/max for vertical scaling
                var mn = pts[0], mx = pts[0]
                for (var i = 1; i < pts.length; i++) {
                    var v = pts[i]
                    if (v === undefined || v === null) continue
                    if (v < mn) mn = v
                    if (v > mx) mx = v
                }
                var range = mx - mn
                if (range < 5) range = 5  // minimum range

                var pad = 4
                var drawW = w - pad * 2
                var drawH = h - pad * 2

                var zc = root.zoneColor

                // Gradient fill under the line
                ctx.beginPath()
                for (var j = 0; j < pts.length; j++) {
                    var px = pad + (j / (pts.length - 1)) * drawW
                    var py = pad + drawH - (((pts[j] || 0) - mn) / range) * drawH
                    if (j === 0) ctx.moveTo(px, py)
                    else ctx.lineTo(px, py)
                }
                ctx.lineTo(pad + drawW, pad + drawH)
                ctx.lineTo(pad, pad + drawH)
                ctx.closePath()
                ctx.fillStyle = Qt.rgba(zc.r, zc.g, zc.b, 0.08)
                ctx.fill()

                // Stroke the line
                ctx.beginPath()
                for (var k = 0; k < pts.length; k++) {
                    var lx = pad + (k / (pts.length - 1)) * drawW
                    var ly = pad + drawH - (((pts[k] || 0) - mn) / range) * drawH
                    if (k === 0) ctx.moveTo(lx, ly)
                    else ctx.lineTo(lx, ly)
                }
                ctx.strokeStyle = zc.toString()
                ctx.lineWidth = 1.5
                ctx.lineJoin = "round"
                ctx.stroke()

                // Latest point dot
                if (pts.length > 0) {
                    var lastIdx = pts.length - 1
                    var lastVal = pts[lastIdx] || 0
                    var dx = pad + (lastIdx / (pts.length - 1)) * drawW
                    var dy = pad + drawH - ((lastVal - mn) / range) * drawH

                    ctx.beginPath()
                    ctx.arc(dx, dy, 3, 0, Math.PI * 2)
                    ctx.fillStyle = zc.toString()
                    ctx.fill()
                }
            }
        }
    }
}
