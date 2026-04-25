import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  InputsWidget — premium throttle/brake/grip overlay.
    Matches Figma: vertical control bars with gradient fills,
    friction circle with reference rings + fading trail,
    steering arc, smoothness bar, lockup/wheelspin with flash.

    Design reference: Figma Make inputs-grpi-overlay
*/
GlassSurface {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 220
    implicitHeight: col.implicitHeight + 24

    // ── Public API ──────────────────────────────────────────────
    property real throttle: 0.0     // 0–1
    property real brake: 0.0        // 0–1
    property real steering: 0.0     // -1 to 1
    property real gForceX: 0.0
    property real gForceY: 0.0
    property bool lockup: false
    property bool wheelspin: false
    property real smoothness: 0.75  // 0–1
    // T161: degraded state — input telemetry stalled (sim
    // disconnected, paused). When true an overlay "SENSOR
    // STALE" banner is shown so the user knows pedal-bars at
    // 0% mean "no data" not "foot off".
    property bool degraded: false

    // G-force trail (ring buffer)
    property var _trail: []
    property bool _pedalOverlap: throttle > 0.05 && brake > 0.05

    onGForceXChanged: _pushTrail()
    onGForceYChanged: _pushTrail()

    function _pushTrail() {
        var t = _trail.slice()
        t.push({ x: gForceX, y: gForceY })
        if (t.length > 30) t.shift()
        _trail = t
        frictionCanvas.requestPaint()
    }

    // ── Inline: Vertical Control Bar ────────────────────────────
    component PedalBar: ColumnLayout {
        property string label: "THR"
        property real value: 0.0
        property color barColor: Theme.Tokens.acidGreen
        spacing: 3
        Layout.alignment: Qt.AlignTop

        Text {
            text: label
            font { family: Theme.Typography.monoFamily; pixelSize: Math.round(8 * root.fontScale); weight: Font.Bold; letterSpacing: 1 }
            color: barColor
            horizontalAlignment: Text.AlignHCenter
            Layout.alignment: Qt.AlignHCenter
        }

        Item {
            Layout.preferredWidth: 18
            Layout.preferredHeight: 72

            Rectangle {
                anchors.fill: parent; radius: 4
                color: Qt.rgba(barColor.r, barColor.g, barColor.b, 0.06)
                border.width: 1
                border.color: Qt.rgba(barColor.r, barColor.g, barColor.b, 0.08)
            }

            // Fill with gradient
            Rectangle {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 1 }
                height: (parent.height - 2) * Math.max(0, Math.min(1, value))
                radius: 3
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(barColor.r, barColor.g, barColor.b, 0.6) }
                    GradientStop { position: 1.0; color: barColor }
                }
                Behavior on height { NumberAnimation { duration: 40 } }
            }

            // Top highlight
            Rectangle {
                anchors { top: parent.top; left: parent.left; right: parent.right }
                height: 1; radius: 4
                color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.06)
            }
        }

        Text {
            text: Math.round(value * 100)
            font { family: Theme.Typography.monoFamily; pixelSize: Math.round(10 * root.fontScale); weight: Font.Bold }
            color: Theme.Tokens.chalk
            horizontalAlignment: Text.AlignHCenter
            Layout.alignment: Qt.AlignHCenter
        }
    }

    // ── Inline: Status indicator with flash ─────────────────────
    component StatusDot: Row {
        property bool active: false
        property color dotColor: Theme.Tokens.safetyRed
        property string label: "LOCK"
        spacing: 4

        Rectangle {
            width: 5; height: 5; radius: 2.5
            anchors.verticalCenter: parent.verticalCenter
            color: active ? dotColor : Qt.rgba(dotColor.r, dotColor.g, dotColor.b, 0.15)
            Behavior on color { ColorAnimation { duration: 100 } }

            // Flash animation when active
            SequentialAnimation on opacity {
                running: active
                loops: Animation.Infinite
                NumberAnimation { to: 0.4; duration: 300 }
                NumberAnimation { to: 1.0; duration: 300 }
            }
            opacity: active ? 1.0 : 1.0
        }
        Text {
            text: label
            font { family: Theme.Typography.monoFamily; pixelSize: Math.round(8 * root.fontScale); weight: Font.Bold; letterSpacing: 0.5 }
            color: active ? dotColor : Theme.Tokens.steel
            Behavior on color { ColorAnimation { duration: 100 } }
        }
    }

    ColumnLayout {
        id: col
        anchors { fill: parent; topMargin: 10; bottomMargin: 8; leftMargin: 12; rightMargin: 12 }
        spacing: 0

        // ── Header: INPUTS + smoothness ────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "INPUTS"
                font { family: Theme.Typography.monoFamily; pixelSize: Math.round(9 * root.fontScale); weight: Font.Bold; letterSpacing: 2 }
                color: Theme.Tokens.steel
            }
            Item { Layout.fillWidth: true }

            // Smoothness bar (green gradient, not purple)
            Row {
                spacing: 1.5
                Repeater {
                    model: 8
                    Rectangle {
                        required property int index
                        width: 4; height: 4; radius: 1
                        color: (index / 8) < root.smoothness
                               ? Qt.rgba(Theme.Tokens.acidGreen.r, Theme.Tokens.acidGreen.g, Theme.Tokens.acidGreen.b,
                                         0.3 + (index / 8) * 0.7)
                               : Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.06)
                    }
                }
            }
        }

        // Separator
        Item {
            Layout.fillWidth: true; Layout.preferredHeight: 8
            Rectangle {
                anchors.centerIn: parent; width: parent.width; height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5; color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.06) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // ── Main: Bars + Friction circle ───────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 110
            spacing: 6

            PedalBar { label: "THR"; value: root.throttle; barColor: Theme.Tokens.acidGreen }
            PedalBar { label: "BRK"; value: root.brake; barColor: Theme.Tokens.safetyRed }

            // Friction circle + steering arc
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 4

                Canvas {
                    id: frictionCanvas
                    Layout.fillWidth: true
                    Layout.preferredHeight: 85

                    onWidthChanged: requestPaint()
                    onHeightChanged: requestPaint()

                    onPaint: {
                        var ctx = getContext("2d")
                        var w = width, h = height
                        var cx = w / 2, cy = h / 2
                        var r = Math.min(cx, cy) - 6
                        ctx.reset()
                        ctx.clearRect(0, 0, w, h)

                        // Reference rings (1G, 2G)
                        for (var ring = 1; ring <= 2; ring++) {
                            ctx.beginPath()
                            ctx.arc(cx, cy, r * ring / 2.5, 0, Math.PI * 2)
                            ctx.strokeStyle = Qt.rgba(0.58, 0.58, 0.58, 0.08)
                            ctx.lineWidth = 0.5
                            ctx.stroke()
                        }

                        // Outer limit
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, 0, Math.PI * 2)
                        ctx.strokeStyle = Qt.rgba(0.58, 0.58, 0.58, 0.15)
                        ctx.lineWidth = 0.8
                        ctx.stroke()

                        // Crosshairs
                        ctx.beginPath()
                        ctx.moveTo(cx - r, cy); ctx.lineTo(cx + r, cy)
                        ctx.moveTo(cx, cy - r); ctx.lineTo(cx, cy + r)
                        ctx.strokeStyle = Qt.rgba(0.58, 0.58, 0.58, 0.06)
                        ctx.lineWidth = 0.5
                        ctx.stroke()

                        // Trail with fade
                        var trail = root._trail
                        if (trail.length > 1) {
                            for (var i = 1; i < trail.length; i++) {
                                var alpha = 0.05 + (i / trail.length) * 0.30
                                ctx.beginPath()
                                ctx.moveTo(cx + trail[i-1].x * r, cy - trail[i-1].y * r)
                                ctx.lineTo(cx + trail[i].x * r, cy - trail[i].y * r)
                                ctx.strokeStyle = Qt.rgba(Theme.Tokens.racingPurple.r, Theme.Tokens.racingPurple.g, Theme.Tokens.racingPurple.b, alpha)
                                ctx.lineWidth = 1.2
                                ctx.stroke()
                            }
                        }

                        // Center apex dot
                        ctx.beginPath()
                        ctx.arc(cx, cy, 1.5, 0, Math.PI * 2)
                        ctx.fillStyle = Qt.rgba(0.58, 0.58, 0.58, 0.3)
                        ctx.fill()

                        // Current G dot + glow
                        var dotX = cx + root.gForceX * r
                        var dotY = cy - root.gForceY * r
                        var grd = ctx.createRadialGradient(dotX, dotY, 0, dotX, dotY, 8)
                        grd.addColorStop(0, Qt.rgba(Theme.Tokens.racingPurple.r, Theme.Tokens.racingPurple.g, Theme.Tokens.racingPurple.b, 0.5))
                        grd.addColorStop(1, "transparent")
                        ctx.beginPath(); ctx.arc(dotX, dotY, 8, 0, Math.PI * 2)
                        ctx.fillStyle = grd; ctx.fill()

                        ctx.beginPath(); ctx.arc(dotX, dotY, 2.5, 0, Math.PI * 2)
                        ctx.fillStyle = Theme.Tokens.racingPurple.toString(); ctx.fill()
                    }
                }

                // Steering arc
                Canvas {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 16
                    onPaint: {
                        var ctx = getContext("2d")
                        var w = width, h = height
                        var cx = w / 2, cy = h
                        var r = w / 2 - 6
                        ctx.reset(); ctx.clearRect(0, 0, w, h)

                        // Arc track
                        ctx.beginPath(); ctx.arc(cx, cy, r, Math.PI, 0)
                        ctx.strokeStyle = Qt.rgba(0.58, 0.58, 0.58, 0.10)
                        ctx.lineWidth = 2; ctx.stroke()

                        // Center tick
                        ctx.beginPath(); ctx.moveTo(cx, cy - r - 2); ctx.lineTo(cx, cy - r + 2)
                        ctx.strokeStyle = Qt.rgba(0.58, 0.58, 0.58, 0.2)
                        ctx.lineWidth = 1; ctx.stroke()

                        // Needle position
                        var angle = Math.PI - (root.steering + 1) * 0.5 * Math.PI
                        var nx = cx + Math.cos(angle) * r
                        var ny = cy + Math.sin(angle) * r
                        ctx.beginPath(); ctx.arc(nx, ny, 2.5, 0, Math.PI * 2)
                        ctx.fillStyle = Theme.Tokens.racingPurple.toString(); ctx.fill()
                    }
                    onWidthChanged: requestPaint()

                    Connections {
                        target: root
                        function onSteeringChanged() { frictionCanvas.parent.children[1].requestPaint() }
                    }
                }
            }
        }

        // Separator
        Item {
            Layout.fillWidth: true; Layout.preferredHeight: 6
            Rectangle {
                anchors.centerIn: parent; width: parent.width; height: 1
                color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.04)
            }
        }

        // ── Bottom: Status dots + G value ──────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            StatusDot { active: root.lockup; dotColor: Theme.Tokens.safetyRed; label: "LOCK" }
            StatusDot { active: root.wheelspin; dotColor: Theme.Tokens.marshalYellow; label: "SPIN" }

            // Pedal overlap warning
            Rectangle {
                visible: root._pedalOverlap
                width: overlapText.implicitWidth + 8; height: 14; radius: 3
                color: Qt.rgba(Theme.Tokens.marshalYellow.r, Theme.Tokens.marshalYellow.g, Theme.Tokens.marshalYellow.b, 0.12)
                Text {
                    id: overlapText; anchors.centerIn: parent
                    text: "OVERLAP"
                    font { family: Theme.Typography.monoFamily; pixelSize: Math.round(7 * root.fontScale); weight: Font.Bold }
                    color: Theme.Tokens.marshalYellow; opacity: 0.7
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: "G " + Math.sqrt(root.gForceX * root.gForceX + root.gForceY * root.gForceY).toFixed(1)
                font { family: Theme.Typography.monoFamily; pixelSize: Math.round(9 * root.fontScale); weight: Font.Bold }
                color: Theme.Tokens.steel
            }
        }
    }

    // ── T161: SENSOR STALE overlay banner ─────────────────────────────
    Rectangle {
        visible: root.degraded
        anchors.centerIn: parent
        width: staleText.implicitWidth + 16
        height: staleText.implicitHeight + 8
        radius: 4
        color: Qt.rgba(Theme.Tokens.marshalYellow.r, Theme.Tokens.marshalYellow.g, Theme.Tokens.marshalYellow.b, 0.15)
        border.width: 1
        border.color: Theme.Tokens.marshalYellow

        Text {
            id: staleText
            anchors.centerIn: parent
            text: "SENSOR STALE"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(10 * root.fontScale)
            font.weight: Font.Bold
            font.letterSpacing: 1.2
            color: Theme.Tokens.marshalYellow
        }
    }
}
