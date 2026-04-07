import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  RadarWidget -- top-down proximity radar (200 x 200).
    Canvas radar with range rings, triangle player car, colored dots
    for nearby cars (ahead vs behind), distance-based opacity,
    direction indicators, animated sweep line.                      */
Rectangle {
    id: root
    width: 200
    height: 200
    color: "transparent"

    // -- public API ----------------------------------------------------------
    property var  cars: []          // [{x, y, isAhead, class}]
    property real range: 30.0       // meters

    // -- null-safe accessors -------------------------------------------------
    readonly property var  safeCars:  cars || []
    readonly property real safeRange: (range > 0) ? range : 30.0

    // -- sweep animation angle -----------------------------------------------
    property real _sweepAngle: 0

    NumberAnimation on _sweepAngle {
        from: 0; to: 360
        duration: 3000
        loops: Animation.Infinite
        running: true
    }

    // -- repaint triggers ----------------------------------------------------
    onSafeCarsChanged:  radar.requestPaint()
    onSafeRangeChanged: radar.requestPaint()
    on_SweepAngleChanged: radar.requestPaint()

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 8
            bottomMargin: 8
            leftMargin: 8
            rightMargin: 8
        }
        spacing: 4

        // -- Header ----------------------------------------------------------
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
                text: root.safeRange.toFixed(0) + " m"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                color: Theme.Tokens.steel
                opacity: 0.7
            }
        }

        // -- Radar canvas ----------------------------------------------------
        Canvas {
            id: radar
            Layout.fillWidth: true
            Layout.fillHeight: true

            onWidthChanged:  requestPaint()
            onHeightChanged: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)

                var cx = width / 2
                var cy = height / 2
                var maxR = Math.min(cx, cy) - 4

                var steelR = Theme.Tokens.steel.r
                var steelG = Theme.Tokens.steel.g
                var steelB = Theme.Tokens.steel.b

                // -- Range rings (3 concentric circles) ----------------------
                ctx.lineWidth = 1
                for (var ring = 1; ring <= 3; ring++) {
                    var r = maxR * (ring / 3)
                    var alpha = 0.06 + (ring * 0.03)
                    ctx.strokeStyle = Qt.rgba(steelR, steelG, steelB, alpha).toString()
                    ctx.beginPath()
                    ctx.arc(cx, cy, r, 0, 2 * Math.PI)
                    ctx.stroke()
                }

                // -- Cross-hairs ---------------------------------------------
                ctx.strokeStyle = Qt.rgba(steelR, steelG, steelB, 0.06).toString()
                ctx.lineWidth = 0.5
                ctx.beginPath()
                ctx.moveTo(cx, cy - maxR); ctx.lineTo(cx, cy + maxR)
                ctx.moveTo(cx - maxR, cy); ctx.lineTo(cx + maxR, cy)
                ctx.stroke()

                // -- Sweep line (rotating scan effect) -----------------------
                var sweepRad = root._sweepAngle * Math.PI / 180
                var sx = cx + Math.cos(sweepRad) * maxR
                var sy = cy - Math.sin(sweepRad) * maxR

                // Sweep gradient tail
                var grad = ctx.createConicalGradient(cx, cy, -root._sweepAngle * Math.PI / 180)
                grad.addColorStop(0, Qt.rgba(Theme.Tokens.acidGreen.r,
                                              Theme.Tokens.acidGreen.g,
                                              Theme.Tokens.acidGreen.b, 0.12).toString())
                grad.addColorStop(0.08, Qt.rgba(Theme.Tokens.acidGreen.r,
                                                 Theme.Tokens.acidGreen.g,
                                                 Theme.Tokens.acidGreen.b, 0.0).toString())
                grad.addColorStop(1, "transparent")

                ctx.fillStyle = grad
                ctx.beginPath()
                ctx.moveTo(cx, cy)
                ctx.arc(cx, cy, maxR, 0, 2 * Math.PI)
                ctx.closePath()
                ctx.fill()

                // Sweep leading edge line
                ctx.strokeStyle = Qt.rgba(Theme.Tokens.acidGreen.r,
                                           Theme.Tokens.acidGreen.g,
                                           Theme.Tokens.acidGreen.b, 0.25).toString()
                ctx.lineWidth = 1
                ctx.beginPath()
                ctx.moveTo(cx, cy)
                ctx.lineTo(sx, sy)
                ctx.stroke()

                // -- Player car (center triangle/arrow) ----------------------
                ctx.fillStyle = Theme.Tokens.acidGreen.toString()
                ctx.beginPath()
                ctx.moveTo(cx, cy - 7)
                ctx.lineTo(cx - 5, cy + 5)
                ctx.lineTo(cx, cy + 2)
                ctx.lineTo(cx + 5, cy + 5)
                ctx.closePath()
                ctx.fill()

                // Faint glow around player
                ctx.fillStyle = Qt.rgba(Theme.Tokens.acidGreen.r,
                                         Theme.Tokens.acidGreen.g,
                                         Theme.Tokens.acidGreen.b, 0.08).toString()
                ctx.beginPath()
                ctx.arc(cx, cy, 10, 0, 2 * Math.PI)
                ctx.fill()

                // -- Nearby cars ---------------------------------------------
                var carList = root.safeCars
                for (var i = 0; i < carList.length; i++) {
                    var car = carList[i]
                    if (!car) continue

                    var carX = car.x || 0
                    var carY = car.y || 0
                    var isAhead = car.isAhead || false

                    var px = (carX / root.safeRange) * maxR
                    var py = -(carY / root.safeRange) * maxR

                    var rawDist = Math.sqrt(px * px + py * py)

                    // Clamp to edge
                    if (rawDist > maxR) {
                        var scale = maxR / rawDist
                        px *= scale
                        py *= scale
                    }

                    var dispDist = Math.min(rawDist, maxR)
                    var proximity = 1.0 - (dispDist / maxR)

                    // Color: ahead = pitOrange, behind = racingPurple
                    var dotColor = isAhead
                        ? Theme.Tokens.pitOrange
                        : Theme.Tokens.racingPurple

                    // Distance-based opacity (closer = more opaque)
                    var dotAlpha = 0.3 + (proximity * 0.7)

                    // Danger glow for very close cars
                    if (proximity > 0.65) {
                        ctx.fillStyle = Qt.rgba(Theme.Tokens.safetyRed.r,
                                                 Theme.Tokens.safetyRed.g,
                                                 Theme.Tokens.safetyRed.b,
                                                 0.10 + proximity * 0.12).toString()
                        ctx.beginPath()
                        ctx.arc(cx + px, cy + py, 9, 0, 2 * Math.PI)
                        ctx.fill()
                    }

                    // Direction indicator (small triangle pointing toward center)
                    var angle = Math.atan2(-py, -px)
                    var triSize = 3
                    var triDist = 7
                    var triX = cx + px + Math.cos(angle) * triDist
                    var triY = cy + py + Math.sin(angle) * triDist

                    ctx.fillStyle = Qt.rgba(dotColor.r, dotColor.g,
                                             dotColor.b, dotAlpha * 0.6).toString()
                    ctx.beginPath()
                    ctx.moveTo(triX + Math.cos(angle) * triSize,
                               triY + Math.sin(angle) * triSize)
                    ctx.lineTo(triX + Math.cos(angle + 2.3) * triSize,
                               triY + Math.sin(angle + 2.3) * triSize)
                    ctx.lineTo(triX + Math.cos(angle - 2.3) * triSize,
                               triY + Math.sin(angle - 2.3) * triSize)
                    ctx.closePath()
                    ctx.fill()

                    // Main dot
                    ctx.fillStyle = Qt.rgba(dotColor.r, dotColor.g,
                                             dotColor.b, dotAlpha).toString()
                    ctx.beginPath()
                    ctx.arc(cx + px, cy + py, 4, 0, 2 * Math.PI)
                    ctx.fill()

                    // Inner bright core
                    ctx.fillStyle = Qt.rgba(dotColor.r, dotColor.g,
                                             dotColor.b,
                                             Math.min(1.0, dotAlpha + 0.3)).toString()
                    ctx.beginPath()
                    ctx.arc(cx + px, cy + py, 1.5, 0, 2 * Math.PI)
                    ctx.fill()
                }
            }

            Component.onCompleted: requestPaint()
        }

        // -- Legend -----------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Layout.alignment: Qt.AlignHCenter

            // Ahead indicator
            Row {
                spacing: 4
                Rectangle {
                    width: 6; height: 6; radius: 3
                    color: Theme.Tokens.pitOrange
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: "AHEAD"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    font.letterSpacing: 0.8
                    color: Theme.Tokens.steel
                    opacity: 0.6
                }
            }

            // Behind indicator
            Row {
                spacing: 4
                Rectangle {
                    width: 6; height: 6; radius: 3
                    color: Theme.Tokens.racingPurple
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: "BEHIND"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    font.letterSpacing: 0.8
                    color: Theme.Tokens.steel
                    opacity: 0.6
                }
            }
        }
    }
}
