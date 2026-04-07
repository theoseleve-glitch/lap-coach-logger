import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  TrackMapWidget — canvas-based track outline with car position dot (240x240).
    Draws a track from normalised {x,y} points and overlays the player car
    position plus nearby car dots.                                              */
Rectangle {
    id: root
    width: 240
    height: 240
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real carPosition: 0.0          // 0-1 lap fraction
    property var  trackPoints: []           // [{x, y}] normalised 0-1
    property var  nearbyPositions: []       // [float] lap fractions

    // ── repaint on data change ──────────────────────────────────────
    onCarPositionChanged:     mapCanvas.requestPaint()
    onTrackPointsChanged:     mapCanvas.requestPaint()
    onNearbyPositionsChanged: mapCanvas.requestPaint()

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
                text: "TRACK MAP"
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

        // ── Map canvas ─────────────────────────────────────────────
        Canvas {
            id: mapCanvas
            Layout.fillWidth: true
            Layout.fillHeight: true

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)

                var pad = 12
                var w = width - pad * 2
                var h = height - pad * 2
                var pts = root.trackPoints || []

                // ── Default oval if no track points ────────────────
                if (pts.length < 3) {
                    var cx = width / 2
                    var cy = height / 2
                    var rx = w * 0.42
                    var ry = h * 0.38

                    ctx.strokeStyle = Qt.rgba(Theme.Tokens.chalk.r,
                                              Theme.Tokens.chalk.g,
                                              Theme.Tokens.chalk.b, 0.15)
                    ctx.lineWidth = 2
                    ctx.beginPath()
                    ctx.ellipse(cx - rx, cy - ry, rx * 2, ry * 2)
                    ctx.stroke()

                    // Player dot on oval
                    var angle = root.carPosition * Math.PI * 2 - Math.PI / 2
                    var px = cx + rx * Math.cos(angle)
                    var py = cy + ry * Math.sin(angle)
                    drawCarDot(ctx, px, py, Theme.Tokens.acidGreen)

                    // Nearby cars on oval
                    var nearby = root.nearbyPositions || []
                    for (var n = 0; n < nearby.length; n++) {
                        var na = nearby[n] * Math.PI * 2 - Math.PI / 2
                        var npx = cx + rx * Math.cos(na)
                        var npy = cy + ry * Math.sin(na)
                        drawCarDot(ctx, npx, npy, Theme.Tokens.pitOrange)
                    }
                    return
                }

                // ── Draw track outline from points ─────────────────
                ctx.strokeStyle = Qt.rgba(Theme.Tokens.chalk.r,
                                          Theme.Tokens.chalk.g,
                                          Theme.Tokens.chalk.b, 0.15)
                ctx.lineWidth = 2
                ctx.lineJoin = "round"
                ctx.beginPath()
                ctx.moveTo(pad + pts[0].x * w, pad + pts[0].y * h)
                for (var i = 1; i < pts.length; i++) {
                    ctx.lineTo(pad + pts[i].x * w, pad + pts[i].y * h)
                }
                ctx.closePath()
                ctx.stroke()

                // ── Interpolate position on track ──────────────────
                function trackPosXY(frac) {
                    var idx = frac * (pts.length - 1)
                    var lo = Math.floor(idx)
                    var hi = Math.min(lo + 1, pts.length - 1)
                    var t = idx - lo
                    return {
                        x: pad + ((1 - t) * pts[lo].x + t * pts[hi].x) * w,
                        y: pad + ((1 - t) * pts[lo].y + t * pts[hi].y) * h
                    }
                }

                // Player car
                var cp = trackPosXY(root.carPosition)
                drawCarDot(ctx, cp.x, cp.y, Theme.Tokens.acidGreen)

                // Nearby cars
                var nearbyList = root.nearbyPositions || []
                for (var j = 0; j < nearbyList.length; j++) {
                    var np2 = trackPosXY(nearbyList[j])
                    drawCarDot(ctx, np2.x, np2.y, Theme.Tokens.pitOrange)
                }
            }

            function drawCarDot(ctx, x, y, col) {
                // Glow
                ctx.fillStyle = Qt.rgba(col.r, col.g, col.b, 0.20)
                ctx.beginPath()
                ctx.arc(x, y, 8, 0, 2 * Math.PI)
                ctx.fill()
                // Core
                ctx.fillStyle = col.toString()
                ctx.beginPath()
                ctx.arc(x, y, 4, 0, 2 * Math.PI)
                ctx.fill()
            }

            Component.onCompleted: requestPaint()
        }
    }
}
