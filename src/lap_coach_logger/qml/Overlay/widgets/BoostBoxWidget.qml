import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  BoostBoxWidget — ERS / KERS boost level indicator (160x100).
    270-degree arc gauge showing available boost energy with mode badge.
    Colors: deploy = acidGreen, harvest = marshalYellow, off = steel.  */
Rectangle {
    id: root
    width: 160
    height: 100
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real   boostLevel: 0.0     // 0-1
    property string boostMode: "off"    // "deploy" | "harvest" | "off"
    property real   maxBoost: 1.0

    // ── null-safe derived ───────────────────────────────────────────
    readonly property real safeLevel: isFinite(boostLevel) ? boostLevel : 0.0
    readonly property real safeMax:   isFinite(maxBoost) && maxBoost > 0
                                      ? maxBoost : 1.0

    readonly property color modeColor: {
        var m = (typeof boostMode === "string") ? boostMode.toLowerCase() : ""
        switch (m) {
        case "deploy":  return Theme.Tokens.acidGreen
        case "harvest": return Theme.Tokens.marshalYellow
        default:        return Theme.Tokens.steel
        }
    }

    // ── repaint on data change + resize ─────────────────────────────
    onSafeLevelChanged: boostCanvas.requestPaint()
    onModeColorChanged: boostCanvas.requestPaint()

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: Theme.Tokens.sm
            bottomMargin: Theme.Tokens.sm
            leftMargin: Theme.Tokens.md
            rightMargin: Theme.Tokens.md
        }
        spacing: 2

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.Tokens.sm

            Text {
                text: "BOOST"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Theme.Typography.microWeight
                font.letterSpacing: Theme.Typography.microSpacing
                color: Theme.Tokens.steel
            }

            // Mode badge
            Rectangle {
                implicitWidth: modeLabel.implicitWidth + Theme.Tokens.md
                implicitHeight: 14
                radius: Theme.Tokens.radiusSm / 2
                color: Theme.Tokens.subtle(root.modeColor, 0.12)
                border.width: 1
                border.color: Theme.Tokens.subtle(root.modeColor, 0.25)

                Text {
                    id: modeLabel
                    anchors.centerIn: parent
                    text: (typeof root.boostMode === "string")
                          ? root.boostMode.toUpperCase() : "OFF"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                    color: root.modeColor
                }
            }

            Item { Layout.fillWidth: true }
        }

        // ── Arc gauge ──────────────────────────────────────────────
        Canvas {
            id: boostCanvas
            Layout.fillWidth: true
            Layout.fillHeight: true

            // repaint on resize
            onWidthChanged:  requestPaint()
            onHeightChanged: requestPaint()

            property real animatedLevel: root.safeLevel
            Behavior on animatedLevel {
                NumberAnimation { duration: Theme.Motion.metricCountUpDuration }
            }
            onAnimatedLevelChanged: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)

                var cx = width / 2
                var cy = height * 0.65
                var r  = Math.min(cx, height * 0.55) - 4
                if (r <= 0) return

                var lineWidth  = 5
                // 270-degree arc: from 135 to 405 degrees
                var startAngle = Math.PI * 0.75
                var endAngle   = Math.PI * 2.25
                var totalAngle = endAngle - startAngle

                // Background arc
                ctx.beginPath()
                ctx.arc(cx, cy, r, startAngle, endAngle)
                ctx.strokeStyle = Theme.Tokens.subtle(Theme.Tokens.chalk, 0.06)
                ctx.lineWidth = lineWidth
                ctx.lineCap = "round"
                ctx.stroke()

                // Filled arc
                var pct = Math.max(0, Math.min(1,
                            animatedLevel / root.safeMax))
                if (pct > 0) {
                    ctx.beginPath()
                    ctx.arc(cx, cy, r,
                            startAngle, startAngle + totalAngle * pct)
                    ctx.strokeStyle = root.modeColor.toString()
                    ctx.lineWidth = lineWidth
                    ctx.lineCap = "round"
                    ctx.stroke()
                }

                // Center percentage text (large mono)
                var mc = root.modeColor
                ctx.fillStyle = mc.toString()
                ctx.font = "bold " + Theme.Typography.headingSize
                          + "px " + Theme.Typography.monoFamily
                ctx.textAlign = "center"
                ctx.textBaseline = "middle"
                ctx.fillText(Math.round(pct * 100) + "%", cx, cy - 2)
            }

            Component.onCompleted: requestPaint()
        }
    }
}
