import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  MiniMapWidget — compact track outline with car dot (180x180).
    Smaller version of TrackMapWidget with no labels, just track + dot.  */
Rectangle {
    id: root
    width: 180
    height: 180
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real carPosition: 0.0      // 0-1 lap fraction
    property var  trackPoints: []       // [{x, y}] normalised 0-1

    // ── repaint on data change ──────────────────────────────────────
    onCarPositionChanged: miniCanvas.requestPaint()
    onTrackPointsChanged: miniCanvas.requestPaint()

    Canvas {
        id: miniCanvas
        anchors {
            fill: parent
            margins: 8
        }

        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.clearRect(0, 0, width, height)

            var pad = 6
            var w = width - pad * 2
            var h = height - pad * 2
            var pts = root.trackPoints || []

            // ── Default oval when no track data ────────────────
            if (pts.length < 3) {
                var cx = width / 2
                var cy = height / 2
                var rx = w * 0.42
                var ry = h * 0.38

                ctx.strokeStyle = Qt.rgba(Theme.Tokens.chalk.r,
                                          Theme.Tokens.chalk.g,
                                          Theme.Tokens.chalk.b, 0.12)
                ctx.lineWidth = 1.5
                ctx.beginPath()
                ctx.ellipse(cx - rx, cy - ry, rx * 2, ry * 2)
                ctx.stroke()

                var angle = root.carPosition * Math.PI * 2 - Math.PI / 2
                var px = cx + rx * Math.cos(angle)
                var py = cy + ry * Math.sin(angle)
                drawDot(ctx, px, py, Theme.Tokens.acidGreen)
                return
            }

            // ── Draw track path ────────────────────────────────
            ctx.strokeStyle = Qt.rgba(Theme.Tokens.chalk.r,
                                      Theme.Tokens.chalk.g,
                                      Theme.Tokens.chalk.b, 0.12)
            ctx.lineWidth = 1.5
            ctx.lineJoin = "round"
            ctx.beginPath()
            ctx.moveTo(pad + pts[0].x * w, pad + pts[0].y * h)
            for (var i = 1; i < pts.length; i++) {
                ctx.lineTo(pad + pts[i].x * w, pad + pts[i].y * h)
            }
            ctx.closePath()
            ctx.stroke()

            // ── Car position ───────────────────────────────────
            var idx = root.carPosition * (pts.length - 1)
            var lo = Math.floor(idx)
            var hi = Math.min(lo + 1, pts.length - 1)
            var t = idx - lo
            var cpx = pad + ((1 - t) * pts[lo].x + t * pts[hi].x) * w
            var cpy = pad + ((1 - t) * pts[lo].y + t * pts[hi].y) * h
            drawDot(ctx, cpx, cpy, Theme.Tokens.acidGreen)
        }

        function drawDot(ctx, x, y, col) {
            ctx.fillStyle = Qt.rgba(col.r, col.g, col.b, 0.20)
            ctx.beginPath()
            ctx.arc(x, y, 6, 0, 2 * Math.PI)
            ctx.fill()

            ctx.fillStyle = col.toString()
            ctx.beginPath()
            ctx.arc(x, y, 3, 0, 2 * Math.PI)
            ctx.fill()
        }

        Component.onCompleted: requestPaint()
    }
}
