import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  DeltaBarWidget -- horizontal delta bar (300 x 60).
    Green left (faster), red right (slower).  Delta number
    centered over the bar with scale markers.                       */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 300
    height: 60
    color: "transparent"

    // -- public API -------------------------------------------------------
    property real delta: 0.0
    property real maxDelta: 2.0

    // -- derived ----------------------------------------------------------
    readonly property real _safeDelta: isFinite(delta) ? delta : 0.0
    readonly property real _safeMax: (isFinite(maxDelta) && maxDelta > 0) ? maxDelta : 2.0
    readonly property real _clampedPct: Math.max(0, Math.min(1,
        Math.abs(_safeDelta) / _safeMax))

    function formatDelta(d) {
        if (!isFinite(d) || d === 0) return "+0.000"
        var sign = d > 0 ? "+" : ""
        return sign + d.toFixed(3)
    }

    readonly property color deltaColor: {
        if (_safeDelta < -0.001) return Theme.Tokens.acidGreen
        if (_safeDelta >  0.001) return Theme.Tokens.safetyRed
        return Theme.Tokens.steel
    }

    // -- inline scale-label component -------------------------------------
    component ScaleLabel: Text {
        property string label: ""
        text: label
        font.family: Theme.Typography.monoFamily
        font.pixelSize: Math.round(7 * root.fontScale)
        font.weight: Font.Bold
        color: Theme.Tokens.steel
        opacity: 0.5
        horizontalAlignment: Text.AlignHCenter
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 6
            bottomMargin: 6
            leftMargin: 14
            rightMargin: 14
        }
        spacing: 2

        // -- Delta number (large, centered) -------------------------------
        Text {
            text: root.formatDelta(root._safeDelta)
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(20 * root.fontScale)
            font.weight: Font.Bold
            color: root.deltaColor
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true

            Behavior on color { ColorAnimation { duration: 200 } }
        }

        // -- Bar ----------------------------------------------------------
        Item {
            id: barContainer
            Layout.fillWidth: true
            Layout.preferredHeight: 16

            // Track background
            Rectangle {
                id: barTrack
                anchors.fill: parent
                radius: 4
                color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.06)
            }

            // Delta fill (Canvas for gradient precision)
            Canvas {
                id: fillCanvas
                anchors.fill: parent
                onPaint: {
                    var ctx = getContext("2d")
                    var w = width, h = height
                    ctx.clearRect(0, 0, w, h)
                    if (w <= 0 || h <= 0) return

                    var center = w / 2
                    var pct = root._clampedPct
                    var fillW = center * pct
                    if (fillW < 1) return

                    var r = 4

                    if (root._safeDelta < -0.001) {
                        // Faster: fill left from center
                        var x0 = center - fillW
                        var grad = ctx.createLinearGradient(x0, 0, center, 0)
                        var gc = Theme.Tokens.acidGreen
                        grad.addColorStop(0.0, Qt.rgba(gc.r, gc.g, gc.b, 0.3))
                        grad.addColorStop(1.0, Qt.rgba(gc.r, gc.g, gc.b, 0.7))
                        ctx.beginPath()
                        ctx.roundedRect(x0, 0, fillW, h, r, r)
                        ctx.fillStyle = grad
                        ctx.fill()
                    } else if (root._safeDelta > 0.001) {
                        // Slower: fill right from center
                        var grad2 = ctx.createLinearGradient(center, 0, center + fillW, 0)
                        var rc = Theme.Tokens.safetyRed
                        grad2.addColorStop(0.0, Qt.rgba(rc.r, rc.g, rc.b, 0.7))
                        grad2.addColorStop(1.0, Qt.rgba(rc.r, rc.g, rc.b, 0.3))
                        ctx.beginPath()
                        ctx.roundedRect(center, 0, fillW, h, r, r)
                        ctx.fillStyle = grad2
                        ctx.fill()
                    }
                }

                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()

                // Smooth repaint on delta changes
                Connections {
                    target: root
                    function onDeltaChanged() { _repaintTimer.restart() }
                    function onMaxDeltaChanged() { _repaintTimer.restart() }
                }

                Timer {
                    id: _repaintTimer
                    interval: 16  // ~60fps throttle
                    onTriggered: fillCanvas.requestPaint()
                }
            }

            // Center line
            Rectangle {
                anchors {
                    horizontalCenter: parent.horizontalCenter
                    top: parent.top
                    bottom: parent.bottom
                }
                width: 2
                color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.25)
                z: 2
            }
        }

        // -- Scale markers ------------------------------------------------
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 10

            ScaleLabel {
                label: "-" + root._safeMax.toFixed(0) + "s"
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
            }

            ScaleLabel {
                label: "-" + (root._safeMax / 2).toFixed(0) + "s"
                x: parent.width * 0.25 - implicitWidth / 2
                anchors.verticalCenter: parent.verticalCenter
            }

            ScaleLabel {
                label: "0"
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.verticalCenter: parent.verticalCenter
                opacity: 0.7
            }

            ScaleLabel {
                label: "+" + (root._safeMax / 2).toFixed(0) + "s"
                x: parent.width * 0.75 - implicitWidth / 2
                anchors.verticalCenter: parent.verticalCenter
            }

            ScaleLabel {
                label: "+" + root._safeMax.toFixed(0) + "s"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        // -- Labels -------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true

            Text {
                text: "FASTER"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(8 * root.fontScale)
                font.weight: Font.Bold
                font.letterSpacing: 1.0
                color: Theme.Tokens.acidGreen
                opacity: 0.6
            }

            Item { Layout.fillWidth: true }

            Text {
                text: "SLOWER"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(8 * root.fontScale)
                font.weight: Font.Bold
                font.letterSpacing: 1.0
                color: Theme.Tokens.safetyRed
                opacity: 0.6
            }
        }
    }
}
