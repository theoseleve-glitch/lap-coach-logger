import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  InputsWidget — throttle / brake / grip overlay.
    Vertical control bars for THR and BRK, a Canvas-based friction circle,
    smoothness indicator, and lockup / wheelspin status dots.               */
GlassSurface {
    id: root
    width: 220
    implicitHeight: col.implicitHeight + 24

    // ── public API ──────────────────────────────────────────────────
    property real throttle: 0.0     // 0-1
    property real brake: 0.0        // 0-1
    property real steering: 0.0     // -1 to 1
    property real gForceX: 0.0
    property real gForceY: 0.0
    property bool lockup: false
    property bool wheelspin: false
    property real smoothness: 0.75  // 0-1

    // G-force trail buffer
    property var _trail: []

    onGForceXChanged: _updateTrail()
    onGForceYChanged: _updateTrail()

    function _updateTrail() {
        var t = _trail.slice()
        t.push({ x: gForceX, y: gForceY })
        if (t.length > 20) t.shift()
        _trail = t
        frictionCanvas.requestPaint()
    }

    ColumnLayout {
        id: col
        anchors {
            fill: parent
            topMargin: 12
            bottomMargin: 10
            leftMargin: 12
            rightMargin: 12
        }
        spacing: 0

        // ── Header: INPUTS label + smoothness bar ──────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: "INPUTS"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            // Smoothness squares
            Row {
                spacing: 2
                Repeater {
                    model: 8
                    Rectangle {
                        required property int index
                        width: 5
                        height: 5
                        radius: 1
                        color: (index / 8) < root.smoothness
                               ? Theme.Tokens.racingPurple
                               : Qt.rgba(Theme.Tokens.chalk.r,
                                         Theme.Tokens.chalk.g,
                                         Theme.Tokens.chalk.b, 0.08)
                    }
                }
            }
        }

        // ── Separator ──────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 9
            Rectangle {
                anchors.centerIn: parent
                width: parent.width
                height: 1
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

        // ── Main: Control bars + Friction circle ───────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 100
            spacing: 8

            // Throttle bar
            ColumnLayout {
                spacing: 3
                Layout.alignment: Qt.AlignTop

                Text {
                    text: "THR"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.Bold
                    color: Theme.Tokens.acidGreen
                    horizontalAlignment: Text.AlignHCenter
                    Layout.alignment: Qt.AlignHCenter
                }

                // Vertical bar container
                Item {
                    Layout.preferredWidth: 16
                    Layout.preferredHeight: 70

                    Rectangle {
                        anchors.fill: parent
                        radius: 3
                        color: Qt.rgba(Theme.Tokens.acidGreen.r,
                                       Theme.Tokens.acidGreen.g,
                                       Theme.Tokens.acidGreen.b, 0.08)
                    }

                    Rectangle {
                        anchors {
                            left: parent.left
                            right: parent.right
                            bottom: parent.bottom
                        }
                        height: parent.height * Math.max(0, Math.min(1, root.throttle))
                        radius: 3
                        color: Theme.Tokens.acidGreen

                        Behavior on height { NumberAnimation { duration: 50 } }
                    }
                }

                Text {
                    text: Math.round(root.throttle * 100) + "%"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    color: Theme.Tokens.chalk
                    horizontalAlignment: Text.AlignHCenter
                    Layout.alignment: Qt.AlignHCenter
                }
            }

            // Brake bar
            ColumnLayout {
                spacing: 3
                Layout.alignment: Qt.AlignTop

                Text {
                    text: "BRK"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.Bold
                    color: Theme.Tokens.safetyRed
                    horizontalAlignment: Text.AlignHCenter
                    Layout.alignment: Qt.AlignHCenter
                }

                Item {
                    Layout.preferredWidth: 16
                    Layout.preferredHeight: 70

                    Rectangle {
                        anchors.fill: parent
                        radius: 3
                        color: Qt.rgba(Theme.Tokens.safetyRed.r,
                                       Theme.Tokens.safetyRed.g,
                                       Theme.Tokens.safetyRed.b, 0.08)
                    }

                    Rectangle {
                        anchors {
                            left: parent.left
                            right: parent.right
                            bottom: parent.bottom
                        }
                        height: parent.height * Math.max(0, Math.min(1, root.brake))
                        radius: 3
                        color: Theme.Tokens.safetyRed

                        Behavior on height { NumberAnimation { duration: 50 } }
                    }
                }

                Text {
                    text: Math.round(root.brake * 100) + "%"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    color: Theme.Tokens.chalk
                    horizontalAlignment: Text.AlignHCenter
                    Layout.alignment: Qt.AlignHCenter
                }
            }

            // Friction circle
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 100

                Canvas {
                    id: frictionCanvas
                    anchors.fill: parent

                    onPaint: {
                        var ctx = getContext("2d")
                        var w = width
                        var h = height
                        var cx = w / 2
                        var cy = h / 2
                        var r = Math.min(cx, cy) - 4   // limit circle radius

                        ctx.reset()
                        ctx.clearRect(0, 0, w, h)

                        // Outer limit circle
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, 0, Math.PI * 2)
                        ctx.strokeStyle = Qt.rgba(Theme.Tokens.chalk.r,
                                                  Theme.Tokens.chalk.g,
                                                  Theme.Tokens.chalk.b, 0.10)
                        ctx.lineWidth = 1
                        ctx.stroke()

                        // Crosshairs
                        ctx.beginPath()
                        ctx.moveTo(cx - r, cy)
                        ctx.lineTo(cx + r, cy)
                        ctx.moveTo(cx, cy - r)
                        ctx.lineTo(cx, cy + r)
                        ctx.strokeStyle = Qt.rgba(Theme.Tokens.chalk.r,
                                                  Theme.Tokens.chalk.g,
                                                  Theme.Tokens.chalk.b, 0.06)
                        ctx.lineWidth = 1
                        ctx.stroke()

                        // G-force trail
                        var trail = root._trail
                        if (trail.length > 1) {
                            ctx.beginPath()
                            for (var i = 0; i < trail.length; i++) {
                                var px = cx + trail[i].x * r
                                var py = cy - trail[i].y * r
                                if (i === 0) ctx.moveTo(px, py)
                                else ctx.lineTo(px, py)
                            }
                            ctx.strokeStyle = Qt.rgba(Theme.Tokens.racingPurple.r,
                                                      Theme.Tokens.racingPurple.g,
                                                      Theme.Tokens.racingPurple.b, 0.35)
                            ctx.lineWidth = 1.5
                            ctx.stroke()
                        }

                        // Current position dot
                        var dotX = cx + root.gForceX * r
                        var dotY = cy - root.gForceY * r

                        // Glow
                        var grd = ctx.createRadialGradient(dotX, dotY, 0, dotX, dotY, 8)
                        grd.addColorStop(0, Qt.rgba(Theme.Tokens.racingPurple.r,
                                                    Theme.Tokens.racingPurple.g,
                                                    Theme.Tokens.racingPurple.b, 0.4))
                        grd.addColorStop(1, "transparent")
                        ctx.beginPath()
                        ctx.arc(dotX, dotY, 8, 0, Math.PI * 2)
                        ctx.fillStyle = grd
                        ctx.fill()

                        // Dot
                        ctx.beginPath()
                        ctx.arc(dotX, dotY, 3, 0, Math.PI * 2)
                        ctx.fillStyle = Theme.Tokens.racingPurple.toString()
                        ctx.fill()
                    }
                }
            }
        }

        // ── Separator ──────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 7
            Rectangle {
                anchors.centerIn: parent
                width: parent.width
                height: 1
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

        // ── Bottom status: LOCK + SPIN + G value ───────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            // Lockup indicator
            Row {
                spacing: 4
                Rectangle {
                    width: 5; height: 5; radius: 2.5
                    color: root.lockup ? Theme.Tokens.safetyRed
                                       : Qt.rgba(Theme.Tokens.safetyRed.r,
                                                  Theme.Tokens.safetyRed.g,
                                                  Theme.Tokens.safetyRed.b, 0.15)
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
                Text {
                    text: "LOCK"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.Bold
                    color: root.lockup ? Theme.Tokens.safetyRed : Theme.Tokens.steel
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
            }

            // Wheelspin indicator
            Row {
                spacing: 4
                Rectangle {
                    width: 5; height: 5; radius: 2.5
                    color: root.wheelspin ? Theme.Tokens.marshalYellow
                                          : Qt.rgba(Theme.Tokens.marshalYellow.r,
                                                    Theme.Tokens.marshalYellow.g,
                                                    Theme.Tokens.marshalYellow.b, 0.15)
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
                Text {
                    text: "SPIN"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.Bold
                    color: root.wheelspin ? Theme.Tokens.marshalYellow : Theme.Tokens.steel
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
            }

            Item { Layout.fillWidth: true }

            // Combined G value
            Text {
                text: Math.sqrt(root.gForceX * root.gForceX
                                + root.gForceY * root.gForceY).toFixed(1) + " G"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 10
                font.weight: Font.Bold
                color: Theme.Tokens.chalk
            }
        }
    }
}
