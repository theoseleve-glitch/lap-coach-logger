import QtQuick
import "../Theme" as Theme

Item {
    id: root

    property var values: []
    property color lineColor: Theme.Tokens.pitOrange
    property real minValue: 0
    property real maxValue: 300
    property int maxPoints: 180

    implicitHeight: 64

    Rectangle {
        anchors.fill: parent
        radius: Theme.Tokens.radiusSm
        color: Qt.rgba(root.lineColor.r, root.lineColor.g, root.lineColor.b, 0.03)
    }

    Canvas {
        id: canvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var w = width
            var h = height

            ctx.clearRect(0, 0, w, h)

            var pts = root.values
            if (!pts || pts.length < 2)
                return

            // Use only the last maxPoints values
            var start = Math.max(0, pts.length - root.maxPoints)
            var visible = pts.slice(start)
            var count = visible.length

            var range = root.maxValue - root.minValue
            if (range <= 0)
                range = 1

            function xOf(i) {
                return (i / (count - 1)) * w
            }
            function yOf(v) {
                return h - ((v - root.minValue) / range) * h
            }

            // Gradient fill below the line
            var grad = ctx.createLinearGradient(0, 0, 0, h)
            grad.addColorStop(0, Qt.rgba(root.lineColor.r, root.lineColor.g,
                                         root.lineColor.b, 0.50))
            grad.addColorStop(1, Qt.rgba(root.lineColor.r, root.lineColor.g,
                                         root.lineColor.b, 0.0))

            ctx.beginPath()
            ctx.moveTo(xOf(0), yOf(visible[0]))
            for (var i = 1; i < count; i++)
                ctx.lineTo(xOf(i), yOf(visible[i]))

            // Close path for fill
            ctx.lineTo(xOf(count - 1), h)
            ctx.lineTo(xOf(0), h)
            ctx.closePath()
            ctx.fillStyle = grad
            ctx.fill()

            // Polyline stroke
            ctx.beginPath()
            ctx.moveTo(xOf(0), yOf(visible[0]))
            for (var j = 1; j < count; j++)
                ctx.lineTo(xOf(j), yOf(visible[j]))

            ctx.strokeStyle = root.lineColor
            ctx.lineWidth = 1.5
            ctx.lineJoin = "round"
            ctx.lineCap = "round"
            ctx.stroke()
        }
    }

    onValuesChanged: canvas.requestPaint()
    onWidthChanged: canvas.requestPaint()
    onHeightChanged: canvas.requestPaint()
    onLineColorChanged: canvas.requestPaint()
    onMinValueChanged: canvas.requestPaint()
    onMaxValueChanged: canvas.requestPaint()
}
