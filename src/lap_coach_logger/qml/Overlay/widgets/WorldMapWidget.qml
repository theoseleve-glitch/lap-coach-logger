import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  WorldMapWidget — simplified world map with track location dot (280 x 160).
    Canvas draws rough continent outlines and places an acidGreen glow dot
    at the given latitude/longitude.  Repaints on lat/lon change and resize.

    Null-safe: handles missing trackName, zero coords gracefully.          */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 280
    height: 160
    color: "transparent"

    // ── Public API ──────────────────────────────────────────────────
    property real   latitude:  0.0
    property real   longitude: 0.0
    property string trackName: ""

    // ── Repaint triggers ────────────────────────────────────────────
    onLatitudeChanged:  mapCanvas.requestPaint()
    onLongitudeChanged: mapCanvas.requestPaint()

    // ── Null-safe helpers ───────────────────────────────────────────
    readonly property bool hasCoords: root.latitude !== 0.0 || root.longitude !== 0.0
    readonly property string safeTrackName: (root.trackName || "").trim()

    function fmtCoord(v, posChar, negChar) {
        if (v === undefined || v === null || isNaN(v)) return "--"
        var abs = Math.abs(v)
        var dir = v >= 0 ? posChar : negChar
        return abs.toFixed(2) + "\u00B0" + dir
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

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.Tokens.sm - 2

            Text {
                text: "LOCATION"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize - 1
                font.weight: Theme.Typography.microWeight
                font.letterSpacing: Theme.Typography.microSpacing - 0.3
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            Text {
                visible: root.safeTrackName.length > 0
                text: root.safeTrackName
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize - 1
                font.weight: Font.DemiBold
                color: Theme.Tokens.chalk
                elide: Text.ElideRight
                Layout.maximumWidth: 160
            }
        }

        // ── Map canvas ─────────────────────────────────────────────
        Canvas {
            id: mapCanvas
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

                // Mercator-ish projection helpers
                function lonToX(lon) { return (lon + 180) / 360 * w }
                function latToY(lat) { return (90 - lat) / 180 * h }

                // ── Simplified continent outlines ─────────────────
                var steelR = Theme.Tokens.steel.r
                var steelG = Theme.Tokens.steel.g
                var steelB = Theme.Tokens.steel.b
                ctx.strokeStyle = Qt.rgba(steelR, steelG, steelB, 0.18)
                ctx.lineWidth = 1
                ctx.lineJoin = "round"

                var continents = [
                    // North America
                    [[-130,50],[-125,60],[-100,65],[-80,60],[-75,45],[-80,30],[-95,25],[-105,20],[-115,30],[-125,40],[-130,50]],
                    // South America
                    [[-80,10],[-70,5],[-60,-5],[-50,-15],[-45,-25],[-50,-35],[-60,-45],[-70,-50],[-75,-40],[-75,-25],[-80,-5],[-80,10]],
                    // Europe
                    [[-10,36],[0,43],[5,48],[10,55],[20,58],[30,60],[35,55],[30,45],[25,38],[15,38],[5,43],[-10,36]],
                    // Africa
                    [[-15,15],[-5,5],[5,-5],[15,-15],[25,-25],[35,-30],[40,-15],[45,5],[40,15],[30,30],[20,35],[5,35],[-5,30],[-15,15]],
                    // Asia
                    [[30,60],[45,55],[60,45],[70,40],[80,30],[90,25],[100,20],[110,25],[120,35],[130,45],[140,50],[130,60],[100,65],[60,65],[30,60]],
                    // Australia
                    [[115,-15],[130,-15],[150,-20],[150,-30],[140,-35],[130,-35],[115,-25],[115,-15]]
                ]

                for (var c = 0; c < continents.length; c++) {
                    var pts = continents[c]
                    ctx.beginPath()
                    for (var p = 0; p < pts.length; p++) {
                        var x = lonToX(pts[p][0])
                        var y = latToY(pts[p][1])
                        if (p === 0) ctx.moveTo(x, y)
                        else ctx.lineTo(x, y)
                    }
                    ctx.closePath()
                    ctx.fillStyle = Qt.rgba(steelR, steelG, steelB, 0.06)
                    ctx.fill()
                    ctx.stroke()
                }

                // ── Track location dot with glow ──────────────────
                if (root.hasCoords) {
                    var dx = lonToX(root.longitude)
                    var dy = latToY(root.latitude)

                    // Glow
                    var grd = ctx.createRadialGradient(dx, dy, 0, dx, dy, 12)
                    grd.addColorStop(0, Qt.rgba(Theme.Tokens.acidGreen.r,
                                                Theme.Tokens.acidGreen.g,
                                                Theme.Tokens.acidGreen.b, 0.35))
                    grd.addColorStop(1, "transparent")
                    ctx.beginPath()
                    ctx.arc(dx, dy, 12, 0, Math.PI * 2)
                    ctx.fillStyle = grd
                    ctx.fill()

                    // Core dot
                    ctx.beginPath()
                    ctx.arc(dx, dy, 3.5, 0, Math.PI * 2)
                    ctx.fillStyle = Theme.Tokens.acidGreen.toString()
                    ctx.fill()

                    // Track name label below dot
                    if (root.safeTrackName.length > 0) {
                        ctx.font = "bold 8px monospace"
                        ctx.fillStyle = Theme.Tokens.chalk.toString()
                        ctx.textAlign = "center"
                        ctx.fillText(root.safeTrackName, dx, dy + 14)
                    }
                }

                // ── Coordinate display (bottom-right) ─────────────
                if (root.hasCoords) {
                    var latStr = root.fmtCoord(root.latitude,  "N", "S")
                    var lonStr = root.fmtCoord(root.longitude, "E", "W")
                    ctx.font = "7px monospace"
                    ctx.fillStyle = Qt.rgba(steelR, steelG, steelB, 0.50)
                    ctx.textAlign = "right"
                    ctx.fillText(latStr + "  " + lonStr, w - 4, h - 4)
                }
            }
        }
    }
}
