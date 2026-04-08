import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  FlagsWidget -- vivid full-panel flag display (160 x 100).
    Green/yellow/red/blue/white/checkered/none with emoji icons,
    pulsing yellow, "LET PASS" on blue, "ALL CLEAR" on none/green,
    Canvas checkered pattern, smooth color transitions.             */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 160
    height: 100
    color: "transparent"

    // -- public API ----------------------------------------------------------
    property string flag: "none"   // green|yellow|red|blue|white|checkered|none

    // -- derived (null-safe) -------------------------------------------------
    readonly property string safeFlag: (flag || "none").toLowerCase()

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

    readonly property string flagLabel: {
        switch (safeFlag) {
        case "green":     return "ALL CLEAR"
        case "yellow":    return "YELLOW"
        case "red":       return "RED"
        case "blue":      return "BLUE"
        case "white":     return "WHITE"
        case "checkered": return "FINISH"
        default:          return "ALL CLEAR"
        }
    }

    readonly property string flagIcon: {
        switch (safeFlag) {
        case "green":     return "\u2705"    // check mark
        case "yellow":    return "\u26A0"    // warning
        case "red":       return "\u26D4"    // no entry
        case "blue":      return "\u{1F6A9}" // flag
        case "white":     return "\u{1F3F3}" // white flag
        case "checkered": return "\u{1F3C1}" // checkered flag
        default:          return "\u2714"    // check
        }
    }

    readonly property string flagSubtitle: {
        switch (safeFlag) {
        case "blue":   return "LET PASS"
        case "green":  return ""
        case "none":   return ""
        default:       return ""
        }
    }

    // -- panel fill opacity: vivid for active flags --------------------------
    readonly property real panelOpacity: {
        switch (safeFlag) {
        case "none":   return 0.0
        case "green":  return 0.10
        default:       return 0.35
        }
    }

    readonly property real borderOpacity: {
        switch (safeFlag) {
        case "none":   return 0.15
        case "green":  return 0.30
        default:       return 0.65
        }
    }

    // -- yellow pulse animation state ----------------------------------------
    property real _pulseOpacity: 1.0

    SequentialAnimation on _pulseOpacity {
        id: pulseAnim
        running: safeFlag === "yellow"
        loops: Animation.Infinite
        NumberAnimation { from: 1.0; to: 0.35; duration: 500;
                          easing.type: Easing.InOutSine }
        NumberAnimation { from: 0.35; to: 1.0; duration: 500;
                          easing.type: Easing.InOutSine }
    }

    onSafeFlagChanged: {
        if (safeFlag !== "yellow") _pulseOpacity = 1.0
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 12
            rightMargin: 12
        }
        spacing: 0

        // -- Header ----------------------------------------------------------
        Text {
            text: "FLAG"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(9 * root.fontScale)
            font.weight: Font.Bold
            font.letterSpacing: 1.2
            color: Theme.Tokens.steel
        }

        Item { Layout.preferredHeight: 6 }

        // -- Flag panel ------------------------------------------------------
        Rectangle {
            id: flagPanel
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.Tokens.radiusSm

            color: safeFlag === "none"
                   ? Theme.Tokens.subtle(Theme.Tokens.steel, 0.08)
                   : safeFlag === "green"
                     ? Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.10)
                     : Qt.rgba(root.flagColor.r, root.flagColor.g,
                               root.flagColor.b, root.panelOpacity)

            border.width: 2
            border.color: Qt.rgba(root.flagColor.r, root.flagColor.g,
                                  root.flagColor.b, root.borderOpacity)

            opacity: (safeFlag === "yellow") ? root._pulseOpacity : 1.0

            Behavior on color  { ColorAnimation { duration: 300; easing.type: Easing.OutCubic } }
            Behavior on border.color { ColorAnimation { duration: 300; easing.type: Easing.OutCubic } }

            // -- Checkered canvas overlay ------------------------------------
            Canvas {
                id: checkerCanvas
                anchors.fill: parent
                visible: safeFlag === "checkered"

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.reset()
                    ctx.clearRect(0, 0, width, height)
                    var sq = 12
                    var cols = Math.ceil(width / sq)
                    var rows = Math.ceil(height / sq)
                    for (var row = 0; row < rows; row++) {
                        for (var col = 0; col < cols; col++) {
                            ctx.fillStyle = ((row + col) % 2 === 0)
                                ? "rgba(240,237,229,0.25)"   // chalk
                                : "rgba(10,11,14,0.30)"       // near-black
                            ctx.fillRect(col * sq, row * sq, sq, sq)
                        }
                    }
                }

                onWidthChanged:  if (visible) requestPaint()
                onHeightChanged: if (visible) requestPaint()
                onVisibleChanged: if (visible) requestPaint()
                Component.onCompleted: requestPaint()
            }

            // -- Subtle green tint for "all clear" ---------------------------
            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                visible: safeFlag === "none" || safeFlag === "green"
                color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.05)
            }

            // -- Label column ------------------------------------------------
            ColumnLayout {
                anchors.centerIn: parent
                spacing: 2

                // Icon + main label row
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 6

                    Text {
                        text: root.flagIcon
                        font.pixelSize: Math.round(16 * root.fontScale)
                        visible: safeFlag !== "none"

                        Behavior on opacity { NumberAnimation { duration: 200 } }
                    }

                    Text {
                        text: root.flagLabel
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Math.round(16 * root.fontScale)
                        font.weight: Font.Bold
                        font.letterSpacing: 2
                        color: (safeFlag === "none" || safeFlag === "green")
                               ? Theme.Tokens.acidGreen
                               : root.flagColor

                        Behavior on color { ColorAnimation { duration: 300 } }
                    }
                }

                // Subtitle (e.g. "LET PASS" for blue)
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    visible: root.flagSubtitle.length > 0
                    text: root.flagSubtitle
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(9 * root.fontScale)
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.5
                    color: Qt.rgba(root.flagColor.r, root.flagColor.g,
                                   root.flagColor.b, 0.80)
                    opacity: visible ? 1.0 : 0.0

                    Behavior on opacity { NumberAnimation { duration: 200 } }
                }
            }
        }
    }
}
