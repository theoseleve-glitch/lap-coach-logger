import QtQuick
import "../../Theme" as Theme

/*  MicVisualizerWidget -- audio level bars for streams (200x60).
    16 vertical bars of varying height reacting to mic input levels.
    Category: streaming -- uses racingPurple accent.                      */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 200
    height: 60
    color: "transparent"

    // -- public API ----------------------------------------------------------
    property var    levels: [0.2,0.4,0.6,0.8,0.9,0.7,0.5,0.3,
                             0.4,0.6,0.7,0.5,0.3,0.6,0.8,0.4]
    property bool   isActive: true
    property string color_: ""

    // -- internal ------------------------------------------------------------
    readonly property color _accent: color_.length > 0
                                     ? color_ : Theme.Tokens.acidGreen

    onLevelsChanged:   visualizerCanvas.requestPaint()
    onIsActiveChanged: visualizerCanvas.requestPaint()

    // -- content -------------------------------------------------------------
    Rectangle {
        anchors.fill: parent
        radius: Theme.Tokens.radiusSm
        color: Qt.rgba(0, 0, 0, 0.55)
        border.width: 1
        border.color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.15)
        clip: true

        // -- Mic label -------------------------------------------------------
        Text {
            anchors {
                top: parent.top; left: parent.left
                topMargin: Theme.Tokens.xs; leftMargin: Theme.Tokens.xs + 2
            }
            text: "MIC"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(7 * root.fontScale)
            font.weight: Font.Bold
            font.letterSpacing: 1.0
            color: Theme.Tokens.steel
            opacity: 0.5
            z: 1
        }

        // -- Active dot ------------------------------------------------------
        Rectangle {
            anchors {
                top: parent.top; right: parent.right
                topMargin: Theme.Tokens.xs + 2; rightMargin: Theme.Tokens.xs + 2
            }
            width: 5; height: 5; radius: 2.5
            color: root.isActive ? root._accent : Theme.Tokens.steel
            z: 1

            SequentialAnimation on opacity {
                running: root.isActive
                loops: Animation.Infinite
                NumberAnimation { from: 1.0; to: 0.3; duration: 600 }
                NumberAnimation { from: 0.3; to: 1.0; duration: 600 }
            }
            // Reset opacity when inactive
            Behavior on opacity {
                enabled: !root.isActive
                NumberAnimation { duration: 200 }
            }
        }

        // -- Visualizer bars (Canvas) ----------------------------------------
        Canvas {
            id: visualizerCanvas
            anchors {
                fill: parent
                topMargin: Theme.Tokens.sm
                bottomMargin: Theme.Tokens.xs + 2
                leftMargin: Theme.Tokens.sm
                rightMargin: Theme.Tokens.sm
            }

            // Repaint on resize
            onWidthChanged:  requestPaint()
            onHeightChanged: requestPaint()
            Component.onCompleted: requestPaint()

            // Animate repaint at ~30fps when active
            Timer {
                interval: 33
                running: root.isActive
                repeat: true
                onTriggered: visualizerCanvas.requestPaint()
            }

            onPaint: {
                var ctx = getContext("2d")
                var w = width
                var h = height
                ctx.reset()
                ctx.clearRect(0, 0, w, h)

                var bars = Array.isArray(root.levels) ? root.levels : []
                var count = bars.length
                if (count < 1) return

                var gap = 2
                var barW = Math.max(2, (w - gap * (count - 1)) / count)
                var c = Qt.color(root._accent)

                for (var i = 0; i < count; i++) {
                    var level = root.isActive
                                ? Math.max(0, Math.min(1, bars[i] || 0))
                                : 0.05
                    var barH = Math.max(2, level * h)
                    var x = i * (barW + gap)
                    var y = h - barH

                    // Gradient from accent to dim
                    var grad = ctx.createLinearGradient(x, y, x, h)
                    grad.addColorStop(0, Qt.rgba(c.r, c.g, c.b, 0.9))
                    grad.addColorStop(1, Qt.rgba(c.r, c.g, c.b, 0.3))

                    ctx.fillStyle = grad
                    ctx.beginPath()
                    ctx.roundedRect(x, y, barW, barH, 1, 1)
                    ctx.fill()
                }
            }
        }
    }
}
