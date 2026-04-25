import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  DigiflagWidget -- digital marshal post indicator (120 x 120).
    LED-style sector number, flag-colored accent strip, message text.
    Canvas LED digit display, null safety throughout.               */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 120
    height: 120
    color: "transparent"

    // -- public API ----------------------------------------------------------
    property string flag: "none"    // green|yellow|red|blue|white|checkered|none
    property int    sector: 0
    property string message: ""
    // T165: degraded state — marshal post stream stalled (sim
    // disconnect). When true an overlay "TELEMETRY STALE"
    // banner is shown so the user knows "CLEAR" might be a
    // stale value.
    property bool degraded: false

    // -- derived (null-safe) -------------------------------------------------
    readonly property string safeFlag: (flag || "none").toLowerCase()
    readonly property int    safeSector: Math.max(0, sector || 0)
    readonly property string safeMessage: message || ""

    readonly property color flagColor: {
        switch (safeFlag) {
        case "green":     return Theme.Tokens.acidGreen
        case "yellow":    return Theme.Tokens.marshalYellow
        case "red":       return Theme.Tokens.safetyRed
        case "blue":      return "#3B82F6"
        case "white":     return Theme.Tokens.chalk
        case "checkered": return Theme.Tokens.chalk
        default:          return Theme.Tokens.steel
        }
    }

    readonly property string flagSymbol: {
        switch (safeFlag) {
        case "green":     return "\u25CF"   // filled circle
        case "yellow":    return "\u26A0"   // warning
        case "red":       return "\u2716"   // heavy X
        case "blue":      return "\u25B6"   // play / yield
        case "white":     return "\u25CB"   // open circle
        case "checkered": return "\u2691"   // flag
        default:          return "\u2014"   // dash
        }
    }

    readonly property string flagName: {
        switch (safeFlag) {
        case "none": return "CLEAR"
        default:     return safeFlag.toUpperCase()
        }
    }

    readonly property bool isActive: safeFlag !== "none"

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 8
            bottomMargin: 8
            leftMargin: 8
            rightMargin: 8
        }
        spacing: 0

        // -- Header label ----------------------------------------------------
        Text {
            text: "MARSHAL POST"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(8 * root.fontScale)
            font.weight: Font.Bold
            font.letterSpacing: 1.0
            color: Theme.Tokens.steel
            opacity: 0.7
            Layout.alignment: Qt.AlignHCenter
        }

        Item { Layout.preferredHeight: 4 }

        // -- LED sector number (Canvas) --------------------------------------
        Canvas {
            id: ledCanvas
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 44
            Layout.preferredHeight: 36

            property string digit: root.safeSector > 0
                                   ? root.safeSector.toString() : "-"
            property color ledColor: root.flagColor

            onDigitChanged:  requestPaint()
            onLedColorChanged: requestPaint()
            onWidthChanged:  requestPaint()
            onHeightChanged: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)

                var c = ledColor || Theme.Tokens.steel

                // LED background glow
                ctx.fillStyle = Qt.rgba(c.r, c.g, c.b, 0.08).toString()
                ctx.beginPath()
                ctx.roundedRect(0, 0, width, height, 4, 4)
                ctx.fill()

                // LED border
                ctx.strokeStyle = Qt.rgba(c.r, c.g, c.b, 0.25).toString()
                ctx.lineWidth = 1
                ctx.beginPath()
                ctx.roundedRect(0.5, 0.5, width - 1, height - 1, 4, 4)
                ctx.stroke()

                // Digit text (LED style: mono, large)
                ctx.fillStyle = c.toString()
                ctx.font = "bold 24px " + Theme.Typography.monoFamily
                ctx.textAlign = "center"
                ctx.textBaseline = "middle"
                ctx.fillText(digit, width / 2, height / 2 + 1)

                // LED scanline effect (faint horizontal lines)
                ctx.strokeStyle = Qt.rgba(0, 0, 0, 0.12).toString()
                ctx.lineWidth = 0.5
                for (var y = 2; y < height; y += 3) {
                    ctx.beginPath()
                    ctx.moveTo(0, y)
                    ctx.lineTo(width, y)
                    ctx.stroke()
                }
            }

            Component.onCompleted: requestPaint()
        }

        Item { Layout.preferredHeight: 4 }

        // -- Accent strip (flag color) ---------------------------------------
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: parent.width * 0.7
            Layout.preferredHeight: 3
            radius: 1.5
            color: root.flagColor
            opacity: root.isActive ? 0.8 : 0.2

            Behavior on color   { ColorAnimation { duration: 300; easing.type: Easing.OutCubic } }
            Behavior on opacity { NumberAnimation { duration: 300 } }
        }

        Item { Layout.preferredHeight: 4 }

        // -- Flag symbol + name row ------------------------------------------
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 4

            Text {
                text: root.flagSymbol
                font.pixelSize: Math.round(12 * root.fontScale)
                color: root.flagColor

                Behavior on color { ColorAnimation { duration: 300 } }
            }

            Text {
                text: root.flagName
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(10 * root.fontScale)
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: root.flagColor
                horizontalAlignment: Text.AlignHCenter

                Behavior on color { ColorAnimation { duration: 300 } }
            }
        }

        Item { Layout.preferredHeight: 2 }

        // -- Message text ----------------------------------------------------
        Text {
            visible: root.safeMessage.length > 0
            text: root.safeMessage
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(8 * root.fontScale)
            font.weight: Font.DemiBold
            color: Theme.Tokens.steel
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            elide: Text.ElideRight
            maximumLineCount: 1
            opacity: visible ? 0.8 : 0.0

            Behavior on opacity { NumberAnimation { duration: 200 } }
        }

        Item { Layout.fillHeight: true }
    }

    // -- T165: TELEMETRY STALE overlay banner -------------------------------
    Rectangle {
        visible: root.degraded
        anchors.centerIn: parent
        width: staleText.implicitWidth + 12
        height: staleText.implicitHeight + 6
        radius: 4
        color: Qt.rgba(Theme.Tokens.marshalYellow.r, Theme.Tokens.marshalYellow.g, Theme.Tokens.marshalYellow.b, 0.20)
        border.width: 1
        border.color: Theme.Tokens.marshalYellow

        Text {
            id: staleText
            anchors.centerIn: parent
            text: "TELEMETRY STALE"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(8 * root.fontScale)
            font.weight: Font.Bold
            font.letterSpacing: 1.0
            color: Theme.Tokens.marshalYellow
        }
    }
}
