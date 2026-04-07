import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  RadarWidget — top-down proximity radar (200 x 200).
    Canvas-based radar showing nearby cars as dots/arrows
    around a center car icon. Range configurable.              */
Rectangle {
    id: root
    width: 200
    height: 200
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property var cars: []       // [{x, y, isAhead, class}]
    property real range: 30.0   // meters

    // ── repaint on data change ──────────────────────────────────────
    onCarsChanged: radar.requestPaint()
    onRangeChanged: radar.requestPaint()

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
                text: "RADAR"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root.range.toFixed(0) + " m"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                color: Theme.Tokens.steel
                opacity: 0.7
            }
        }

        // ── Radar canvas ───────────────────────────────────────────
        Canvas {
            id: radar
            Layout.fillWidth: true
            Layout.fillHeight: true

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)

                var cx = width / 2
                var cy = height / 2
                var maxR = Math.min(cx, cy) - 4

                // ── Range rings ────────────────────────────────────
                ctx.strokeStyle = Qt.rgba(Theme.Tokens.steel.r,
                                          Theme.Tokens.steel.g,
                                          Theme.Tokens.steel.b, 0.12)
                ctx.lineWidth = 1
                for (var ring = 1; ring <= 3; ring++) {
                    var r = maxR * (ring / 3)
                    ctx.beginPath()
                    ctx.arc(cx, cy, r, 0, 2 * Math.PI)
                    ctx.stroke()
                }

                // ── Cross-hairs ────────────────────────────────────
                ctx.strokeStyle = Qt.rgba(Theme.Tokens.steel.r,
                                          Theme.Tokens.steel.g,
                                          Theme.Tokens.steel.b, 0.08)
                ctx.beginPath()
                ctx.moveTo(cx, cy - maxR)
                ctx.lineTo(cx, cy + maxR)
                ctx.moveTo(cx - maxR, cy)
                ctx.lineTo(cx + maxR, cy)
                ctx.stroke()

                // ── Player car (center) ────────────────────────────
                ctx.fillStyle = Theme.Tokens.acidGreen.toString()
                ctx.beginPath()
                ctx.moveTo(cx, cy - 6)
                ctx.lineTo(cx - 4, cy + 4)
                ctx.lineTo(cx + 4, cy + 4)
                ctx.closePath()
                ctx.fill()

                // ── Nearby cars ────────────────────────────────────
                var carList = root.cars || []
                for (var i = 0; i < carList.length; i++) {
                    var car = carList[i]
                    var px = (car.x / root.range) * maxR
                    var py = -(car.y / root.range) * maxR  // y inverted

                    var dist = Math.sqrt(px * px + py * py)
                    if (dist > maxR) {
                        // Clamp to edge
                        px = px / dist * maxR
                        py = py / dist * maxR
                    }

                    var dotColor
                    if (car.isAhead) {
                        dotColor = Theme.Tokens.pitOrange
                    } else {
                        dotColor = Theme.Tokens.safetyRed
                    }

                    // Danger glow for close cars
                    var proximity = 1 - (dist / maxR)
                    if (proximity > 0.7) {
                        ctx.fillStyle = Qt.rgba(dotColor.r, dotColor.g,
                                                dotColor.b, 0.15)
                        ctx.beginPath()
                        ctx.arc(cx + px, cy + py, 8, 0, 2 * Math.PI)
                        ctx.fill()
                    }

                    // Dot
                    ctx.fillStyle = dotColor.toString()
                    ctx.beginPath()
                    ctx.arc(cx + px, cy + py, 4, 0, 2 * Math.PI)
                    ctx.fill()
                }
            }

            Component.onCompleted: requestPaint()
        }
    }
}
