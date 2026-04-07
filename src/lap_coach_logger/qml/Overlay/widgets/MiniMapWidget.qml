import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  MiniMapWidget -- compact track outline with car dot (180 x 180).
    No labels, just track outline + player dot.
    Canvas with oval fallback, repaint on data change + resize.
    Null safety on trackPoints and carPosition.                     */
Rectangle {
    id: root
    width: 180
    height: 180
    color: "transparent"

    // -- public API ------------------------------------------------------
    property real carPosition: 0.0      // 0-1 lap fraction
    property var  trackPoints: []       // [{x, y}] normalised 0-1

    // -- null-safe accessors ---------------------------------------------
    readonly property var _safePts: {
        var p = root.trackPoints
        return (p && Array.isArray(p)) ? p : []
    }
    readonly property real _safeCarPos: {
        var c = root.carPosition
        return (typeof c === "number" && isFinite(c)) ? Math.max(0, Math.min(1, c)) : 0
    }

    // -- repaint triggers ------------------------------------------------
    onCarPositionChanged: miniCanvas.requestPaint()
    onTrackPointsChanged: miniCanvas.requestPaint()

    Canvas {
        id: miniCanvas
        anchors {
            fill: parent
            margins: Theme.Tokens.sm
        }

        // repaint on resize
        onWidthChanged:  requestPaint()
        onHeightChanged: requestPaint()

        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.clearRect(0, 0, width, height)

            var pad = Theme.Tokens.sm
            var w   = width  - pad * 2
            var h   = height - pad * 2
            var pts = root._safePts

            if (pts.length < 3) {
                _drawOval(ctx, pad, w, h)
            } else {
                _drawTrack(ctx, pad, w, h, pts)
            }
        }

        // -- oval fallback -----------------------------------------------
        function _drawOval(ctx, pad, w, h) {
            var cx = width  / 2
            var cy = height / 2
            var rx = w * 0.42
            var ry = h * 0.38

            ctx.strokeStyle = Theme.Tokens.subtle(Theme.Tokens.chalk, 0.12)
            ctx.lineWidth   = 1.5
            ctx.beginPath()
            ctx.ellipse(cx - rx, cy - ry, rx * 2, ry * 2)
            ctx.stroke()

            var angle = root._safeCarPos * Math.PI * 2 - Math.PI / 2
            var px = cx + rx * Math.cos(angle)
            var py = cy + ry * Math.sin(angle)
            _drawDot(ctx, px, py)
        }

        // -- track from points -------------------------------------------
        function _drawTrack(ctx, pad, w, h, pts) {
            ctx.strokeStyle = Theme.Tokens.subtle(Theme.Tokens.chalk, 0.12)
            ctx.lineWidth   = 1.5
            ctx.lineJoin    = "round"
            ctx.beginPath()
            ctx.moveTo(pad + pts[0].x * w, pad + pts[0].y * h)
            for (var i = 1; i < pts.length; i++) {
                ctx.lineTo(pad + pts[i].x * w, pad + pts[i].y * h)
            }
            ctx.closePath()
            ctx.stroke()

            // Interpolate car position
            var idx = root._safeCarPos * (pts.length - 1)
            var lo  = Math.floor(idx)
            var hi  = Math.min(lo + 1, pts.length - 1)
            var t   = idx - lo
            var cpx = pad + ((1 - t) * pts[lo].x + t * pts[hi].x) * w
            var cpy = pad + ((1 - t) * pts[lo].y + t * pts[hi].y) * h
            _drawDot(ctx, cpx, cpy)
        }

        // -- car dot (pitOrange with glow) -------------------------------
        function _drawDot(ctx, x, y) {
            // Glow
            ctx.fillStyle = Qt.rgba(Theme.Tokens.pitOrange.r,
                                    Theme.Tokens.pitOrange.g,
                                    Theme.Tokens.pitOrange.b, 0.20)
            ctx.beginPath()
            ctx.arc(x, y, 6, 0, 2 * Math.PI)
            ctx.fill()
            // Core
            ctx.fillStyle = Theme.Tokens.pitOrange.toString()
            ctx.beginPath()
            ctx.arc(x, y, 3, 0, 2 * Math.PI)
            ctx.fill()
        }

        Component.onCompleted: requestPaint()
    }
}
