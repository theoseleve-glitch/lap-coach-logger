import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  FuelWidget — fuel strategy overlay (164 px wide).
    Shows remaining fuel, laps left with a 270-degree arc gauge, consumption
    rate, tank percentage, strategy-state capsule (SAFE / TIGHT / SAVE / BOX)
    with pulse on critical, and animated pit window text.                     */
GlassSurface {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 164
    implicitHeight: col.implicitHeight + 24

    // ── public API ──────────────────────────────────────────────────
    property real   remaining: 0.0
    property real   tankCapacity: 0.0
    property real   lapsLeft: 0.0
    property real   fuelPerLap: 0.0
    property string state: "SAFE"       // SAFE | TIGHT | SAVE | BOX
    property string pitWindow: ""
    property int    totalLaps: 0
    property int    currentLap: 0
    // T158: degraded state — fuel telemetry stalled or
    // unavailable. When true the widget renders all data-
    // bearing fields with `--` placeholders in steel colour,
    // distinguishing "no fuel data" from "0 L in green".
    property bool   degraded: false

    // ── state color mapping ─────────────────────────────────────────
    readonly property color stateColor: {
        switch (root.state) {
        case "TIGHT": return Theme.Tokens.marshalYellow
        case "SAVE":  return Theme.Tokens.pitOrange
        case "BOX":   return Theme.Tokens.safetyRed
        default:      return Theme.Tokens.acidGreen
        }
    }

    readonly property bool isCritical: root.state === "BOX"
    readonly property real tankPercent: (root.tankCapacity > 0)
                                        ? Math.max(0, Math.min(1, root.remaining / root.tankCapacity))
                                        : 0

    // ── Inline component: gradient separator (DRY) ──────────────────
    component GradientSeparator: Item {
        Layout.fillWidth: true
        Layout.preferredHeight: 9
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

    // ── Inline component: labeled data row (DRY) ────────────────────
    component DataRow: RowLayout {
        property string label: ""
        property string value: ""
        property color  valueColor: Theme.Tokens.chalk

        Layout.fillWidth: true

        Text {
            text: parent.label
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(9 * root.fontScale)
            font.weight: Font.Bold
            font.letterSpacing: 1.0
            color: Theme.Tokens.steel
        }
        Item { Layout.fillWidth: true }
        Text {
            text: parent.value
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(13 * root.fontScale)
            font.weight: Font.Bold
            color: parent.valueColor
            Behavior on color { ColorAnimation { duration: 200 } }
        }
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

        // ── Header: FUEL + state dot ───────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "FUEL"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(9 * root.fontScale)
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            Rectangle {
                width: 5; height: 5; radius: 2.5
                color: root.stateColor
                Layout.alignment: Qt.AlignVCenter
                Behavior on color { ColorAnimation { duration: 200 } }
            }

            Item { Layout.fillWidth: true }
        }

        // ── Hero: 270-degree fuel arc + LAPS LEFT ──────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 80
            Layout.topMargin: 4

            Canvas {
                id: fuelArc
                anchors.fill: parent

                property real animatedLaps: root.lapsLeft
                Behavior on animatedLaps { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }

                onAnimatedLapsChanged: requestPaint()
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
                Component.onCompleted: requestPaint()

                onPaint: {
                    var ctx = getContext("2d")
                    var w = width
                    var h = height
                    if (w <= 0 || h <= 0) return
                    ctx.reset()
                    ctx.clearRect(0, 0, w, h)

                    var cx = w / 2
                    var cy = h * 0.55
                    var r = 32
                    var lineWidth = 4

                    // 270-degree arc sweep (Figma spec)
                    var sweepDeg = 270
                    var gapDeg = (360 - sweepDeg) / 2
                    var startAngle = (90 + gapDeg) * (Math.PI / 180)
                    var endAngle = startAngle + sweepDeg * (Math.PI / 180)

                    // Background arc
                    ctx.beginPath()
                    ctx.arc(cx, cy, r, startAngle, endAngle)
                    ctx.strokeStyle = Theme.Tokens.subtle(Theme.Tokens.chalk, 0.06).toString()
                    ctx.lineWidth = lineWidth
                    ctx.lineCap = "round"
                    ctx.stroke()

                    // Filled arc -- proportion of laps left / total (or max 30)
                    var max = root.totalLaps > 0 ? root.totalLaps : 30
                    var pct = Math.max(0, Math.min(1, animatedLaps / max))
                    if (pct > 0) {
                        var sc = root.stateColor
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, startAngle, startAngle + (endAngle - startAngle) * pct)
                        ctx.strokeStyle = (sc ? sc.toString() : Theme.Tokens.acidGreen.toString())
                        ctx.lineWidth = lineWidth
                        ctx.lineCap = "round"
                        ctx.stroke()
                    }
                }
            }

            // Overlay text inside arc
            ColumnLayout {
                anchors.centerIn: parent
                anchors.verticalCenterOffset: -2
                spacing: 0

                Text {
                    text: "LAPS LEFT"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(7 * root.fontScale)
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                    color: Theme.Tokens.steel
                    horizontalAlignment: Text.AlignHCenter
                    Layout.alignment: Qt.AlignHCenter
                }
                Text {
                    text: root.degraded
                          ? "--.-"
                          : ((root.lapsLeft !== undefined && !isNaN(root.lapsLeft))
                             ? root.lapsLeft.toFixed(1) : "--.-")
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(20 * root.fontScale)
                    font.weight: Font.Bold
                    color: root.degraded ? Theme.Tokens.steel : root.stateColor
                    horizontalAlignment: Text.AlignHCenter
                    Layout.alignment: Qt.AlignHCenter
                    Behavior on color { ColorAnimation { duration: 200 } }
                }
            }
        }

        // ── Tank percentage bar ────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 6
            Layout.topMargin: 2
            Layout.bottomMargin: 2
            visible: root.tankCapacity > 0

            Rectangle {
                anchors.fill: parent
                radius: 3
                color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.06)
            }

            Rectangle {
                anchors {
                    left: parent.left
                    top: parent.top
                    bottom: parent.bottom
                }
                width: parent.width * root.tankPercent
                radius: 3
                color: root.stateColor
                opacity: 0.7

                Behavior on width  { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
                Behavior on color  { ColorAnimation  { duration: 200 } }
            }

            Text {
                anchors.centerIn: parent
                text: Math.round(root.tankPercent * 100) + "%"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(7 * root.fontScale)
                font.weight: Font.Bold
                color: Theme.Tokens.chalk
                visible: parent.width >= 40
            }
        }

        GradientSeparator {}

        // ── Data rows: REMAINING + FUEL/LAP ────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6

            DataRow {
                label: "REMAINING"
                value: root.degraded
                       ? "-- L"
                       : ((root.remaining !== undefined && !isNaN(root.remaining))
                          ? root.remaining.toFixed(1) + " L" : "-- L")
                valueColor: root.degraded ? Theme.Tokens.steel : Theme.Tokens.chalk
            }

            DataRow {
                label: "FUEL/LAP"
                value: root.degraded
                       ? "-- L"
                       : ((root.fuelPerLap !== undefined && !isNaN(root.fuelPerLap))
                          ? root.fuelPerLap.toFixed(2) + " L" : "-- L")
                valueColor: root.degraded ? Theme.Tokens.steel : Theme.Tokens.chalk
            }
        }

        GradientSeparator {}

        // ── Strategy capsule ───────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            // State badge with critical pulse
            Rectangle {
                id: stateBadge
                implicitWidth: badgeText.implicitWidth + 12
                implicitHeight: 18
                radius: 4
                color: Theme.Tokens.subtle(root.stateColor, 0.12)
                border.width: 1
                border.color: Theme.Tokens.subtle(root.stateColor, 0.25)

                Behavior on color        { ColorAnimation { duration: 200 } }
                Behavior on border.color { ColorAnimation { duration: 200 } }

                // Pulse animation when BOX (critical)
                SequentialAnimation on opacity {
                    id: pulseAnim
                    running: root.isCritical
                    loops: Animation.Infinite
                    NumberAnimation { from: 1.0; to: 0.45; duration: 600; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 0.45; to: 1.0; duration: 600; easing.type: Easing.InOutSine }
                }

                // Reset opacity when not critical
                Binding {
                    target: stateBadge
                    property: "opacity"
                    value: 1.0
                    when: !root.isCritical
                }

                Text {
                    id: badgeText
                    anchors.centerIn: parent
                    text: root.state || "SAFE"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(9 * root.fontScale)
                    font.weight: Font.Bold
                    font.letterSpacing: 1.0
                    color: root.stateColor
                    Behavior on color { ColorAnimation { duration: 200 } }
                }
            }

            // Pit window text with animate in/out
            Text {
                id: pitWindowText
                text: root.pitWindow || ""
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(9 * root.fontScale)
                font.weight: Font.DemiBold
                color: Theme.Tokens.steel
                elide: Text.ElideRight
                Layout.fillWidth: true

                opacity: (root.pitWindow && root.pitWindow.length > 0) ? 1.0 : 0.0
                Behavior on opacity {
                    NumberAnimation { duration: 250; easing.type: Easing.OutCubic }
                }

                // Slide in from left
                transform: Translate {
                    x: (root.pitWindow && root.pitWindow.length > 0) ? 0 : -8
                    Behavior on x {
                        NumberAnimation { duration: 250; easing.type: Easing.OutCubic }
                    }
                }
            }
        }
    }
}
