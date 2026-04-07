import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  InputTelemetryWidget — detailed input view (280 x 180).
    Throttle/brake/clutch vertical bars, steering arc Canvas,
    gear display, RPM bar with redline zone.

    Inline component: PedalBar
    Canvas repaints on steering, rpm, gear, and resize changes.
    Null safety on all numeric inputs.                                */
Rectangle {
    id: root
    width: 280
    height: 180
    color: "transparent"

    // ── Public API ──────────────────────────────────────────────────
    property real throttle: 0.0   // 0-1
    property real brake: 0.0      // 0-1
    property real clutch: 0.0     // 0-1
    property real steering: 0.0   // -1 to 1
    property int  gear: 0
    property real rpm: 0.0
    property real maxRpm: 8000.0

    // ── Null-safe clampers ──────────────────────────────────────────
    function clamp01(v) { return Math.max(0, Math.min(1, v || 0)) }
    function safeRpm()    { return Math.max(0, root.rpm || 0) }
    function safeMaxRpm() { return Math.max(1, root.maxRpm || 8000) }

    // ── Repaint triggers ────────────────────────────────────────────
    onSteeringChanged: steerCanvas.requestPaint()
    onRpmChanged:      steerCanvas.requestPaint()
    onGearChanged:     steerCanvas.requestPaint()

    // ── Derived ─────────────────────────────────────────────────────
    readonly property string gearText: {
        if (root.gear === 0)  return "N"
        if (root.gear === -1) return "R"
        return String(root.gear)
    }

    // ── Inline component: PedalBar ──────────────────────────────────
    component PedalBar: ColumnLayout {
        property string label
        property real   value: 0.0   // 0-1
        property color  barColor

        readonly property real clamped: root.clamp01(value)

        spacing: 3

        Text {
            text: label
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 7
            font.weight: Font.Bold
            color: barColor
            horizontalAlignment: Text.AlignHCenter
            Layout.alignment: Qt.AlignHCenter
        }

        Item {
            Layout.preferredWidth: 14
            Layout.preferredHeight: 65

            Rectangle {
                anchors.fill: parent
                radius: 3
                color: Theme.Tokens.subtle(barColor, 0.08)
            }

            Rectangle {
                anchors {
                    left: parent.left
                    right: parent.right
                    bottom: parent.bottom
                }
                height: parent.height * clamped
                radius: 3
                color: barColor
                Behavior on height { NumberAnimation { duration: 50; easing.type: Easing.OutQuad } }
            }
        }

        Text {
            text: Math.round(clamped * 100) + "%"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 8
            font.weight: Font.Bold
            color: Theme.Tokens.chalk
            horizontalAlignment: Text.AlignHCenter
            Layout.alignment: Qt.AlignHCenter
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

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.Tokens.sm - 2

            Text {
                text: "INPUT TELEMETRY"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize - 1
                font.weight: Theme.Typography.microWeight
                font.letterSpacing: Theme.Typography.microSpacing - 0.3
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            // Gear display (header)
            Text {
                text: root.gearText
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 18
                font.weight: Font.Bold
                color: Theme.Tokens.chalk
                Behavior on text { SequentialAnimation {
                    NumberAnimation { target: gearLabel; property: "opacity"; to: 0.5; duration: 40 }
                    NumberAnimation { target: gearLabel; property: "opacity"; to: 1.0; duration: 80 }
                }}
                id: gearLabel
            }
        }

        // ── Separator ──────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.Tokens.sm - 2
            Rectangle {
                anchors.centerIn: parent
                width: parent.width; height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5; color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // ── Main: Pedal bars + Steering arc ────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.Tokens.sm + 2

            // ── Pedal bars ─────────────────────────────────────────
            RowLayout {
                spacing: Theme.Tokens.sm - 2
                Layout.alignment: Qt.AlignTop

                PedalBar {
                    label: "THR"
                    value: root.throttle
                    barColor: Theme.Tokens.acidGreen
                }

                PedalBar {
                    label: "BRK"
                    value: root.brake
                    barColor: Theme.Tokens.safetyRed
                }

                PedalBar {
                    label: "CLT"
                    value: root.clutch
                    barColor: Theme.Tokens.racingPurple
                }
            }

            // ── Steering arc + RPM Canvas ──────────────────────────
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                Canvas {
                    id: steerCanvas
                    anchors.fill: parent

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

                        var chalkR = Theme.Tokens.chalk.r
                        var chalkG = Theme.Tokens.chalk.g
                        var chalkB = Theme.Tokens.chalk.b
                        var cx = w / 2
                        var cy = h * 0.55
                        var r = Math.min(cx, cy) - 8

                        // Background arc (180 degrees, top half)
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, Math.PI, 2 * Math.PI)
                        ctx.strokeStyle = Qt.rgba(chalkR, chalkG, chalkB, 0.08)
                        ctx.lineWidth = 4
                        ctx.lineCap = "round"
                        ctx.stroke()

                        // Centre tick
                        ctx.beginPath()
                        ctx.moveTo(cx, cy - r - 4)
                        ctx.lineTo(cx, cy - r + 4)
                        ctx.strokeStyle = Qt.rgba(chalkR, chalkG, chalkB, 0.15)
                        ctx.lineWidth = 1
                        ctx.stroke()

                        // Steering needle — angle maps -1..1 to PI..2PI
                        var steerVal = Math.max(-1, Math.min(1, root.steering || 0))
                        var angle = Math.PI + (steerVal + 1) / 2 * Math.PI
                        var nx = cx + Math.cos(angle) * (r - 2)
                        var ny = cy + Math.sin(angle) * (r - 2)

                        // Needle line
                        ctx.beginPath()
                        ctx.moveTo(cx, cy)
                        ctx.lineTo(nx, ny)
                        ctx.strokeStyle = Theme.Tokens.pitOrange.toString()
                        ctx.lineWidth = 2
                        ctx.lineCap = "round"
                        ctx.stroke()

                        // Needle dot
                        ctx.beginPath()
                        ctx.arc(nx, ny, 4, 0, Math.PI * 2)
                        ctx.fillStyle = Theme.Tokens.pitOrange.toString()
                        ctx.fill()

                        // Steering angle text
                        ctx.font = "bold 10px monospace"
                        ctx.fillStyle = Theme.Tokens.chalk.toString()
                        ctx.textAlign = "center"
                        var deg = Math.round(steerVal * 180)
                        ctx.fillText(deg + "\u00B0", cx, cy + 14)

                        // ── RPM bar at bottom ─────────────────────
                        var barY = h - 8
                        var barW = w - 16
                        var barH = 3
                        var barX = 8

                        // Track
                        ctx.fillStyle = Qt.rgba(chalkR, chalkG, chalkB, 0.06)
                        ctx.fillRect(barX, barY, barW, barH)

                        // Redline zone indicator (last 10%)
                        ctx.fillStyle = Qt.rgba(Theme.Tokens.safetyRed.r,
                                                Theme.Tokens.safetyRed.g,
                                                Theme.Tokens.safetyRed.b, 0.08)
                        ctx.fillRect(barX + barW * 0.9, barY, barW * 0.1, barH)

                        // RPM fill
                        var rpmPct = root.safeMaxRpm() > 0
                                     ? Math.min(1, root.safeRpm() / root.safeMaxRpm())
                                     : 0
                        var rpmColor = rpmPct > 0.9  ? Theme.Tokens.safetyRed
                                     : rpmPct > 0.75 ? Theme.Tokens.pitOrange
                                     : Theme.Tokens.acidGreen
                        ctx.fillStyle = rpmColor.toString()
                        ctx.fillRect(barX, barY, barW * rpmPct, barH)

                        // RPM text
                        ctx.font = "7px monospace"
                        ctx.fillStyle = Qt.rgba(Theme.Tokens.steel.r,
                                                Theme.Tokens.steel.g,
                                                Theme.Tokens.steel.b, 0.50)
                        ctx.textAlign = "right"
                        ctx.fillText(Math.round(root.safeRpm()) + " RPM", barX + barW, barY - 3)
                    }
                }
            }
        }
    }
}
