import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  DigiflagWidget — digital flag indicator (120 x 120).
    Numbered flag with sector info, like a digital marshal post.
    Shows the flag state, sector number, and optional message.   */
Rectangle {
    id: root
    width: 120
    height: 120
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property string flag: "none"   // green|yellow|red|blue|white|checkered|none
    property int sector: 0
    property string message: ""

    // ── flag color mapping ──────────────────────────────────────────
    readonly property color flagColor: {
        switch (flag) {
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
        switch (flag) {
        case "green":     return "\u25CF"   // filled circle
        case "yellow":    return "\u26A0"   // warning
        case "red":       return "\u2716"   // heavy X
        case "blue":      return "\u25B6"   // play / yield
        case "white":     return "\u25CB"   // open circle
        case "checkered": return "\u2691"   // flag
        default:          return "\u2014"   // dash
        }
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 10
            rightMargin: 10
        }
        spacing: 0

        // ── Sector indicator ───────────────────────────────────────
        Text {
            visible: root.sector > 0
            text: "S" + root.sector
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 9
            font.weight: Font.Bold
            font.letterSpacing: 1.0
            color: Theme.Tokens.steel
            Layout.alignment: Qt.AlignHCenter
        }

        Item { Layout.preferredHeight: 4 }

        // ── Flag symbol (hero) ─────────────────────────────────────
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 56
            height: 56
            radius: 8
            color: Qt.rgba(root.flagColor.r,
                           root.flagColor.g,
                           root.flagColor.b, 0.15)
            border.width: 2
            border.color: Qt.rgba(root.flagColor.r,
                                  root.flagColor.g,
                                  root.flagColor.b, 0.40)

            Behavior on color { ColorAnimation { duration: 300 } }
            Behavior on border.color { ColorAnimation { duration: 300 } }

            Text {
                anchors.centerIn: parent
                text: root.flagSymbol
                font.pixelSize: 24
                color: root.flagColor

                Behavior on color { ColorAnimation { duration: 300 } }
            }
        }

        Item { Layout.preferredHeight: 4 }

        // ── Flag name ──────────────────────────────────────────────
        Text {
            text: root.flag === "none" ? "CLEAR" : root.flag.toUpperCase()
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 10
            font.weight: Font.Bold
            font.letterSpacing: 1.2
            color: root.flagColor
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true

            Behavior on color { ColorAnimation { duration: 300 } }
        }

        // ── Message ────────────────────────────────────────────────
        Text {
            visible: root.message.length > 0
            text: root.message
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 8
            font.weight: Font.DemiBold
            color: Theme.Tokens.steel
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            Layout.topMargin: 2
            elide: Text.ElideRight
        }
    }
}
