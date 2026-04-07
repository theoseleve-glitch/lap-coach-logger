import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  LaptimeSpreadWidget -- horizontal range bar (300 x 160).
    Shows spread between fastest and slowest lap times with
    Canvas-based markers for current and average.                    */
Rectangle {
    id: root
    width: 300
    height: 160
    color: "transparent"

    // -- public API -------------------------------------------------------
    property real fastestTime: 0.0
    property real slowestTime: 0.0
    property real currentTime: 0.0
    property real averageTime: 0.0

    // -- derived ----------------------------------------------------------
    readonly property real spread: {
        var s = slowestTime - fastestTime
        return (s > 0 && isFinite(s)) ? s : 0
    }
    readonly property bool hasData: fastestTime > 0 && slowestTime > 0

    // -- helpers ----------------------------------------------------------
    function formatTime(s) {
        if (!isFinite(s) || s <= 0) return "-:---.---"
        var mins = Math.floor(s / 60)
        var secs = s - mins * 60
        return mins + ":" + (secs < 10 ? "0" : "") + secs.toFixed(3)
    }

    function positionPct(t) {
        if (spread < 0.001 || !isFinite(t) || t <= 0) return 0.5
        return Math.max(0, Math.min(1, (t - fastestTime) / spread))
    }

    // -- inline data-row component ----------------------------------------
    component DataRow: RowLayout {
        property string label: ""
        property string value: ""
        property color valueColor: Theme.Tokens.chalk

        Layout.fillWidth: true
        spacing: 0

        Text {
            text: label
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 9
            font.weight: Font.Bold
            font.letterSpacing: 1.0
            color: Theme.Tokens.steel
        }
        Item { Layout.fillWidth: true }
        Text {
            text: value
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 13
            font.weight: Font.Bold
            color: valueColor
        }
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 14
            rightMargin: 14
        }
        spacing: 6

        // -- Header -------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "LAP TIME SPREAD"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root.spread > 0
                      ? root.spread.toFixed(3) + "s"
                      : "--"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 11
                font.weight: Font.Bold
                color: Theme.Tokens.pitOrange
            }
        }

        // -- Canvas range bar ---------------------------------------------
        Item {
            id: barArea
            Layout.fillWidth: true
            Layout.preferredHeight: 52

            Canvas {
                id: spreadCanvas
                anchors.fill: parent
                onPaint: {
                    var ctx = getContext("2d")
                    var w = width, h = height
                    ctx.clearRect(0, 0, w, h)
                    if (w <= 0 || h <= 0) return

                    var trackY = h * 0.45
                    var trackH = 6
                    var trackR = 3
                    var pad = 4 // left/right padding for marker labels

                    // -- track background --
                    ctx.beginPath()
                    ctx.roundedRect(pad, trackY, w - pad * 2, trackH, trackR, trackR)
                    var chk = Theme.Tokens.chalk
                    ctx.fillStyle = Qt.rgba(chk.r, chk.g, chk.b, 0.06)
                    ctx.fill()

                    // -- gradient fill --
                    if (root.hasData) {
                        var grad = ctx.createLinearGradient(pad, 0, w - pad, 0)
                        grad.addColorStop(0.0, Qt.rgba(Theme.Tokens.acidGreen.r,
                                                       Theme.Tokens.acidGreen.g,
                                                       Theme.Tokens.acidGreen.b, 0.4))
                        grad.addColorStop(0.5, Qt.rgba(Theme.Tokens.pitOrange.r,
                                                       Theme.Tokens.pitOrange.g,
                                                       Theme.Tokens.pitOrange.b, 0.4))
                        grad.addColorStop(1.0, Qt.rgba(Theme.Tokens.safetyRed.r,
                                                       Theme.Tokens.safetyRed.g,
                                                       Theme.Tokens.safetyRed.b, 0.4))
                        ctx.beginPath()
                        ctx.roundedRect(pad, trackY, w - pad * 2, trackH, trackR, trackR)
                        ctx.fillStyle = grad
                        ctx.fill()
                    }

                    var barW = w - pad * 2

                    // -- helper: draw marker --
                    function drawMarker(pct, color, shape, label) {
                        var mx = pad + barW * pct
                        ctx.fillStyle = color
                        ctx.strokeStyle = color

                        if (shape === "diamond") {
                            // diamond for fastest
                            ctx.save()
                            ctx.translate(mx, trackY + trackH / 2)
                            ctx.rotate(Math.PI / 4)
                            ctx.fillRect(-4, -4, 8, 8)
                            ctx.restore()
                        } else if (shape === "triangle") {
                            // downward triangle for slowest
                            ctx.beginPath()
                            ctx.moveTo(mx, trackY - 4)
                            ctx.lineTo(mx - 5, trackY - 12)
                            ctx.lineTo(mx + 5, trackY - 12)
                            ctx.closePath()
                            ctx.fill()
                        } else if (shape === "line") {
                            // vertical line for average
                            ctx.beginPath()
                            ctx.moveTo(mx, trackY - 8)
                            ctx.lineTo(mx, trackY + trackH + 8)
                            ctx.lineWidth = 1.5
                            ctx.globalAlpha = 0.7
                            ctx.stroke()
                            ctx.globalAlpha = 1.0
                        } else if (shape === "circle") {
                            // circle for current
                            ctx.beginPath()
                            ctx.arc(mx, trackY + trackH / 2, 5, 0, Math.PI * 2)
                            ctx.fill()
                            ctx.beginPath()
                            ctx.arc(mx, trackY + trackH / 2, 5, 0, Math.PI * 2)
                            ctx.lineWidth = 2
                            ctx.strokeStyle = Qt.rgba(0, 0, 0, 0.3)
                            ctx.stroke()
                        }

                        // label
                        if (label) {
                            ctx.fillStyle = color
                            ctx.font = "bold 8px " + Theme.Typography.monoFamily
                            ctx.textAlign = "center"
                            ctx.fillText(label, mx, trackY + trackH + 18)
                        }
                    }

                    if (root.hasData) {
                        // Fastest marker (diamond, acidGreen)
                        drawMarker(root.positionPct(root.fastestTime),
                                   Theme.Tokens.acidGreen, "diamond", "FAST")

                        // Slowest marker (triangle, safetyRed)
                        drawMarker(root.positionPct(root.slowestTime),
                                   Theme.Tokens.safetyRed, "triangle", "SLOW")

                        // Average marker (line, steel)
                        if (root.averageTime > 0) {
                            drawMarker(root.positionPct(root.averageTime),
                                       Theme.Tokens.steel, "line", "AVG")
                        }

                        // Current marker (circle, pitOrange)
                        if (root.currentTime > 0) {
                            drawMarker(root.positionPct(root.currentTime),
                                       Theme.Tokens.pitOrange, "circle", "CUR")
                        }
                    }
                }

                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
            }

            // Repaint when data changes
            Connections {
                target: root
                function onFastestTimeChanged() { spreadCanvas.requestPaint() }
                function onSlowestTimeChanged() { spreadCanvas.requestPaint() }
                function onCurrentTimeChanged() { spreadCanvas.requestPaint() }
                function onAverageTimeChanged() { spreadCanvas.requestPaint() }
            }
        }

        // -- Divider ------------------------------------------------------
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 6
            Rectangle {
                anchors.centerIn: parent
                width: parent.width
                height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5; color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // -- Data rows (extracted to component) ---------------------------
        DataRow {
            label: "FASTEST"
            value: root.formatTime(root.fastestTime)
            valueColor: Theme.Tokens.acidGreen
        }

        DataRow {
            label: "SLOWEST"
            value: root.formatTime(root.slowestTime)
            valueColor: Theme.Tokens.safetyRed
        }

        DataRow {
            label: "AVERAGE"
            value: root.formatTime(root.averageTime)
            valueColor: Theme.Tokens.steel
        }

        DataRow {
            label: "CURRENT"
            value: root.formatTime(root.currentTime)
            valueColor: Theme.Tokens.pitOrange
        }
    }
}
