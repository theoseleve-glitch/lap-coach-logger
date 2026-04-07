import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  InputTelemetryWidget — detailed input view (280x180).
    Throttle/brake/clutch vertical bars, steering arc, gear + RPM display.  */
Rectangle {
    id: root
    width: 280
    height: 180
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property real throttle: 0.0   // 0-1
    property real brake: 0.0      // 0-1
    property real clutch: 0.0     // 0-1
    property real steering: 0.0   // -1 to 1
    property int  gear: 0
    property real rpm: 0.0
    property real maxRpm: 8000.0

    onSteeringChanged: steerCanvas.requestPaint()

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 8
            bottomMargin: 8
            leftMargin: 10
            rightMargin: 10
        }
        spacing: 4

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "INPUT TELEMETRY"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            // Gear display
            Text {
                text: root.gear === 0 ? "N" : (root.gear === -1 ? "R" : root.gear)
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 18
                font.weight: Font.Bold
                color: Theme.Tokens.chalk
            }
        }

        // ── Separator ──────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 6
            Rectangle {
                anchors.centerIn: parent
                width: parent.width; height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5; color: Qt.rgba(Theme.Tokens.chalk.r,
                                                                  Theme.Tokens.chalk.g,
                                                                  Theme.Tokens.chalk.b, 0.08) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // ── Main: Pedal bars + Steering arc ────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            // ── Pedal bars ─────────────────────────────────────────
            RowLayout {
                spacing: 6
                Layout.alignment: Qt.AlignTop

                // Throttle
                PedalBar {
                    label: "THR"
                    value: root.throttle
                    barColor: Theme.Tokens.acidGreen
                }

                // Brake
                PedalBar {
                    label: "BRK"
                    value: root.brake
                    barColor: Theme.Tokens.safetyRed
                }

                // Clutch
                PedalBar {
                    label: "CLT"
                    value: root.clutch
                    barColor: Theme.Tokens.racingPurple
                }
            }

            // ── Steering arc ───────────────────────────────────────
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                Canvas {
                    id: steerCanvas
                    anchors.fill: parent

                    Component.onCompleted: requestPaint()

                    onPaint: {
                        var ctx = getContext("2d")
                        var w = width
                        var h = height
                        ctx.reset()
                        ctx.clearRect(0, 0, w, h)

                        var cx = w / 2
                        var cy = h * 0.55
                        var r = Math.min(cx, cy) - 8

                        // Background arc (180 degrees, top half)
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, Math.PI, 2 * Math.PI)
                        ctx.strokeStyle = Qt.rgba(Theme.Tokens.chalk.r,
                                                  Theme.Tokens.chalk.g,
                                                  Theme.Tokens.chalk.b, 0.08)
                        ctx.lineWidth = 4
                        ctx.lineCap = "round"
                        ctx.stroke()

                        // Centre tick
                        ctx.beginPath()
                        ctx.moveTo(cx, cy - r - 4)
                        ctx.lineTo(cx, cy - r + 4)
                        ctx.strokeStyle = Qt.rgba(Theme.Tokens.chalk.r,
                                                  Theme.Tokens.chalk.g,
                                                  Theme.Tokens.chalk.b, 0.15)
                        ctx.lineWidth = 1
                        ctx.stroke()

                        // Steering needle — angle maps -1..1 to PI..2PI
                        var angle = Math.PI + (root.steering + 1) / 2 * Math.PI
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
                        var deg = Math.round(root.steering * 180)
                        ctx.fillText(deg + "\u00B0", cx, cy + 14)

                        // RPM bar at bottom
                        var barY = h - 8
                        var barW = w - 16
                        var barH = 3
                        var barX = 8

                        // Background
                        ctx.fillStyle = Qt.rgba(Theme.Tokens.chalk.r,
                                                Theme.Tokens.chalk.g,
                                                Theme.Tokens.chalk.b, 0.06)
                        ctx.fillRect(barX, barY, barW, barH)

                        // Fill
                        var rpmPct = root.maxRpm > 0 ? Math.min(1, root.rpm / root.maxRpm) : 0
                        var rpmColor = rpmPct > 0.9 ? Theme.Tokens.safetyRed
                                     : rpmPct > 0.75 ? Theme.Tokens.pitOrange
                                     : Theme.Tokens.acidGreen
                        ctx.fillStyle = rpmColor.toString()
                        ctx.fillRect(barX, barY, barW * rpmPct, barH)
                    }
                }
            }
        }
    }

    // ── Reusable pedal bar component ──────────────────────────────
    component PedalBar: ColumnLayout {
        property string label
        property real   value: 0.0   // 0-1
        property color  barColor

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
                color: Qt.rgba(barColor.r, barColor.g, barColor.b, 0.08)
            }

            Rectangle {
                anchors {
                    left: parent.left
                    right: parent.right
                    bottom: parent.bottom
                }
                height: parent.height * Math.max(0, Math.min(1, value))
                radius: 3
                color: barColor
                Behavior on height { NumberAnimation { duration: 50 } }
            }
        }

        Text {
            text: Math.round(value * 100) + "%"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 8
            font.weight: Font.Bold
            color: Theme.Tokens.chalk
            horizontalAlignment: Text.AlignHCenter
            Layout.alignment: Qt.AlignHCenter
        }
    }
}
