import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  FuelWidget — fuel strategy overlay (164 px wide).
    Shows remaining fuel, laps left with an arc gauge, consumption rate,
    and a strategy-state capsule (SAFE / TIGHT / SAVE / BOX).              */
GlassSurface {
    id: root
    width: 164
    implicitHeight: col.implicitHeight + 24

    // ── public API ──────────────────────────────────────────────────
    property real   remaining: 0.0
    property real   lapsLeft: 0.0
    property real   fuelPerLap: 0.0
    property string state: "SAFE"       // SAFE | TIGHT | SAVE | BOX
    property string pitWindow: ""
    property int    totalLaps: 0
    property int    currentLap: 0

    // ── state color mapping ─────────────────────────────────────────
    readonly property color stateColor: {
        switch (state) {
        case "TIGHT": return Theme.Tokens.marshalYellow
        case "SAVE":  return Theme.Tokens.pitOrange
        case "BOX":   return Theme.Tokens.safetyRed
        default:      return Theme.Tokens.acidGreen
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
                font.pixelSize: 9
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

        // ── Hero: fuel arc + LAPS LEFT ─────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 80
            Layout.topMargin: 4

            Canvas {
                id: fuelArc
                anchors.fill: parent

                property real animatedLaps: root.lapsLeft
                Behavior on animatedLaps { NumberAnimation { duration: 300 } }

                onAnimatedLapsChanged: requestPaint()
                Component.onCompleted: requestPaint()

                onPaint: {
                    var ctx = getContext("2d")
                    var w = width
                    var h = height
                    ctx.reset()
                    ctx.clearRect(0, 0, w, h)

                    var cx = w / 2
                    var cy = h * 0.55
                    var r = 32
                    var lineWidth = 4
                    var startAngle = Math.PI * 0.75
                    var endAngle = Math.PI * 2.25
                    var totalAngle = endAngle - startAngle

                    // Background arc
                    ctx.beginPath()
                    ctx.arc(cx, cy, r, startAngle, endAngle)
                    ctx.strokeStyle = Qt.rgba(Theme.Tokens.chalk.r,
                                              Theme.Tokens.chalk.g,
                                              Theme.Tokens.chalk.b, 0.06)
                    ctx.lineWidth = lineWidth
                    ctx.lineCap = "round"
                    ctx.stroke()

                    // Filled arc — proportion of laps left / total (or max 30)
                    var max = root.totalLaps > 0 ? root.totalLaps : 30
                    var pct = Math.max(0, Math.min(1, animatedLaps / max))
                    if (pct > 0) {
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, startAngle, startAngle + totalAngle * pct)
                        ctx.strokeStyle = root.stateColor.toString()
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
                    font.pixelSize: 7
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                    color: Theme.Tokens.steel
                    horizontalAlignment: Text.AlignHCenter
                    Layout.alignment: Qt.AlignHCenter
                }
                Text {
                    text: root.lapsLeft.toFixed(1)
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 20
                    font.weight: Font.Bold
                    color: root.stateColor
                    horizontalAlignment: Text.AlignHCenter
                    Layout.alignment: Qt.AlignHCenter
                    Behavior on color { ColorAnimation { duration: 200 } }
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

        // ── Data rows: REMAINING + FUEL/LAP ────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6

            // Remaining
            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "REMAINING"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    font.letterSpacing: 1.0
                    color: Theme.Tokens.steel
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: root.remaining.toFixed(1) + " L"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 13
                    font.weight: Font.Bold
                    color: Theme.Tokens.chalk
                }
            }

            // Fuel per lap
            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "FUEL/LAP"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    font.letterSpacing: 1.0
                    color: Theme.Tokens.steel
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: root.fuelPerLap.toFixed(2) + " L"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 13
                    font.weight: Font.Bold
                    color: Theme.Tokens.chalk
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

        // ── Strategy capsule ───────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            // State badge
            Rectangle {
                implicitWidth: badgeText.implicitWidth + 12
                implicitHeight: 18
                radius: 4
                color: Qt.rgba(root.stateColor.r,
                               root.stateColor.g,
                               root.stateColor.b, 0.12)
                border.width: 1
                border.color: Qt.rgba(root.stateColor.r,
                                      root.stateColor.g,
                                      root.stateColor.b, 0.25)

                Behavior on color { ColorAnimation { duration: 200 } }
                Behavior on border.color { ColorAnimation { duration: 200 } }

                Text {
                    id: badgeText
                    anchors.centerIn: parent
                    text: root.state
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    font.letterSpacing: 1.0
                    color: root.stateColor
                    Behavior on color { ColorAnimation { duration: 200 } }
                }
            }

            // Pit window text
            Text {
                visible: root.pitWindow.length > 0
                text: root.pitWindow
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.DemiBold
                color: Theme.Tokens.steel
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }
    }
}
