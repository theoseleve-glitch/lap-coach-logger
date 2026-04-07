import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  TrackMapWidget -- canvas-based track outline with car dots (240 x 240).
    Draws track from normalised {x,y} points; falls back to oval if none.
    Player car as pitOrange dot with glow, nearby cars as smaller steel dots.
    Start/finish line marker. Track direction arrows.
    Repaint on carPosition, trackPoints, nearbyPositions change + resize.   */
Rectangle {
    id: root
    width: 240
    height: 240
    color: "transparent"

    // -- public API ------------------------------------------------------
    property real carPosition:     0.0     // 0-1 lap fraction
    property var  trackPoints:     []      // [{x, y}] normalised 0-1
    property var  nearbyPositions: []      // [float] lap fractions

    // -- null-safe accessors ---------------------------------------------
    readonly property var _safePts: {
        var p = root.trackPoints
        return (p && Array.isArray(p)) ? p : []
    }
    readonly property var _safeNearby: {
        var n = root.nearbyPositions
        return (n && Array.isArray(n)) ? n : []
    }
    readonly property real _safeCarPos: {
        var c = root.carPosition
        return (typeof c === "number" && isFinite(c)) ? Math.max(0, Math.min(1, c)) : 0
    }

    // -- repaint triggers ------------------------------------------------
    onCarPositionChanged:     mapCanvas.requestPaint()
    onTrackPointsChanged:     mapCanvas.requestPaint()
    onNearbyPositionsChanged: mapCanvas.requestPaint()

    // -- layout ----------------------------------------------------------
    ColumnLayout {
        anchors {
            fill: parent
            topMargin:    Theme.Tokens.sm
            bottomMargin: Theme.Tokens.sm
            leftMargin:   Theme.Tokens.sm
            rightMargin:  Theme.Tokens.sm
        }
        spacing: Theme.Tokens.xs

        // -- Header ------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.Tokens.sm

            Text {
                text: "TRACK MAP"
                font.family:       Theme.Typography.monoFamily
                font.pixelSize:    Theme.Typography.microSize
                font.weight:       Font.Bold
                font.letterSpacing: Theme.Typography.microSpacing
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            Text {
                text: Math.round(root._safeCarPos * 100) + "%"
                font.family:    Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                color: Theme.Tokens.steel
                opacity: 0.7
            }
        }

        // -- Map canvas --------------------------------------------------
        Canvas {
            id: mapCanvas
            Layout.fillWidth:  true
            Layout.fillHeight: true

            // repaint on resize
            onWidthChanged:  requestPaint()
            onHeightChanged: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)

                var pad = Theme.Tokens.md
                var w   = width  - pad * 2
                var h   = height - pad * 2
                var pts = root._safePts

                if (pts.length < 3) {
                    _drawOval(ctx, pad, w, h)
                } else {
                    _drawTrack(ctx, pad, w, h, pts)
                }
            }

            // -- oval fallback -------------------------------------------
            function _drawOval(ctx, pad, w, h) {
                var cx = width  / 2
                var cy = height / 2
                var rx = w * 0.42
                var ry = h * 0.38

                // Track outline
                ctx.strokeStyle = Theme.Tokens.subtle(Theme.Tokens.chalk, 0.15)
                ctx.lineWidth   = 2
                ctx.beginPath()
                ctx.ellipse(cx - rx, cy - ry, rx * 2, ry * 2)
                ctx.stroke()

                // Start/finish marker at top
                _drawStartFinish(ctx, cx, cy - ry)

                // Direction arrow (clockwise hint at right)
                _drawArrow(ctx, cx + rx, cy, Math.PI / 2)

                // Player dot on oval
                var angle = root._safeCarPos * Math.PI * 2 - Math.PI / 2
                var px = cx + rx * Math.cos(angle)
                var py = cy + ry * Math.sin(angle)
                _drawPlayerDot(ctx, px, py)

                // Nearby cars on oval
                var nearby = root._safeNearby
                for (var n = 0; n < nearby.length; n++) {
                    var frac = Number(nearby[n]) || 0
                    var na = frac * Math.PI * 2 - Math.PI / 2
                    _drawNearbyDot(ctx, cx + rx * Math.cos(na),
                                        cy + ry * Math.sin(na))
                }
            }

            // -- track from points ---------------------------------------
            function _drawTrack(ctx, pad, w, h, pts) {
                // Track outline
                ctx.strokeStyle = Theme.Tokens.subtle(Theme.Tokens.chalk, 0.15)
                ctx.lineWidth   = 2
                ctx.lineJoin    = "round"
                ctx.beginPath()
                ctx.moveTo(pad + pts[0].x * w, pad + pts[0].y * h)
                for (var i = 1; i < pts.length; i++) {
                    ctx.lineTo(pad + pts[i].x * w, pad + pts[i].y * h)
                }
                ctx.closePath()
                ctx.stroke()

                // Start/finish marker at first point
                _drawStartFinish(ctx, pad + pts[0].x * w, pad + pts[0].y * h)

                // Direction arrows at ~25% and ~75% of track
                var q1 = Math.floor(pts.length * 0.25)
                var q3 = Math.floor(pts.length * 0.75)
                if (q1 > 0 && q1 < pts.length - 1) {
                    var a1 = Math.atan2(
                        (pts[q1 + 1].y - pts[q1 - 1].y) * h,
                        (pts[q1 + 1].x - pts[q1 - 1].x) * w
                    )
                    _drawArrow(ctx, pad + pts[q1].x * w, pad + pts[q1].y * h, a1)
                }
                if (q3 > 0 && q3 < pts.length - 1) {
                    var a3 = Math.atan2(
                        (pts[q3 + 1].y - pts[q3 - 1].y) * h,
                        (pts[q3 + 1].x - pts[q3 - 1].x) * w
                    )
                    _drawArrow(ctx, pad + pts[q3].x * w, pad + pts[q3].y * h, a3)
                }

                // Interpolate position on track
                function trackPosXY(frac) {
                    var idx = frac * (pts.length - 1)
                    var lo  = Math.floor(idx)
                    var hi  = Math.min(lo + 1, pts.length - 1)
                    var t   = idx - lo
                    return {
                        x: pad + ((1 - t) * pts[lo].x + t * pts[hi].x) * w,
                        y: pad + ((1 - t) * pts[lo].y + t * pts[hi].y) * h
                    }
                }

                // Player car
                var cp = trackPosXY(root._safeCarPos)
                _drawPlayerDot(ctx, cp.x, cp.y)

                // Nearby cars
                var nearbyList = root._safeNearby
                for (var j = 0; j < nearbyList.length; j++) {
                    var frac = Number(nearbyList[j]) || 0
                    var np = trackPosXY(frac)
                    _drawNearbyDot(ctx, np.x, np.y)
                }
            }

            // -- player dot (pitOrange with glow) ------------------------
            function _drawPlayerDot(ctx, x, y) {
                // Glow
                ctx.fillStyle = Qt.rgba(Theme.Tokens.pitOrange.r,
                                        Theme.Tokens.pitOrange.g,
                                        Theme.Tokens.pitOrange.b, 0.25)
                ctx.beginPath()
                ctx.arc(x, y, 10, 0, 2 * Math.PI)
                ctx.fill()
                // Core
                ctx.fillStyle = Theme.Tokens.pitOrange.toString()
                ctx.beginPath()
                ctx.arc(x, y, 5, 0, 2 * Math.PI)
                ctx.fill()
            }

            // -- nearby dot (smaller, steel) -----------------------------
            function _drawNearbyDot(ctx, x, y) {
                ctx.fillStyle = Qt.rgba(Theme.Tokens.steel.r,
                                        Theme.Tokens.steel.g,
                                        Theme.Tokens.steel.b, 0.50)
                ctx.beginPath()
                ctx.arc(x, y, 3, 0, 2 * Math.PI)
                ctx.fill()
            }

            // -- start/finish line marker --------------------------------
            function _drawStartFinish(ctx, x, y) {
                var halfLen = 6
                ctx.strokeStyle = Theme.Tokens.chalk.toString()
                ctx.lineWidth   = 2
                ctx.beginPath()
                ctx.moveTo(x - halfLen, y)
                ctx.lineTo(x + halfLen, y)
                ctx.stroke()
            }

            // -- direction arrow -----------------------------------------
            function _drawArrow(ctx, x, y, angle) {
                var sz = 5
                ctx.save()
                ctx.translate(x, y)
                ctx.rotate(angle)
                ctx.fillStyle = Qt.rgba(Theme.Tokens.chalk.r,
                                        Theme.Tokens.chalk.g,
                                        Theme.Tokens.chalk.b, 0.30)
                ctx.beginPath()
                ctx.moveTo(sz, 0)
                ctx.lineTo(-sz, -sz * 0.6)
                ctx.lineTo(-sz, sz * 0.6)
                ctx.closePath()
                ctx.fill()
                ctx.restore()
            }

            Component.onCompleted: requestPaint()
        }
    }
}
