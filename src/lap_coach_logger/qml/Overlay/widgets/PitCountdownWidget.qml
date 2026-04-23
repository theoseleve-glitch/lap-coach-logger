import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  PitCountdownWidget — pit call overlay (240 x 80).

    Three display modes driven by `severity`:
      - "advisory"  → "PIT IN 3" + fuel sub-text, calm amber
      - "critical"  → "PIT NEXT LAP" / "BOX BOX BOX", red with pulse
      - "ok"        → hidden (handled via `visible` binding by parent)

    Degraded rendering: if headline is empty, render a muted "—" so the
    widget never looks broken when the user has it enabled outside a
    pit window.                                                          */
Rectangle {
    id: root

    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 240
    height: 80
    color: "transparent"

    // -- public API -------------------------------------------------------
    property string headline: ""          // "PIT IN 3" / "BOX BOX BOX"
    property string sub: ""               // "38L · Keep tires"
    property string severity: "ok"        // "ok" / "advisory" / "critical"

    // -- derived ----------------------------------------------------------
    readonly property bool isCritical: severity === "critical"
    readonly property bool hasContent: headline.length > 0
    readonly property color accentColor: {
        if (severity === "critical") return Theme.Tokens.safetyRed
        if (severity === "advisory") return Theme.Tokens.marshalYellow
        return Theme.Tokens.steel
    }

    // Background panel with accent-tinted fill on critical
    Rectangle {
        anchors.fill: parent
        radius: 10
        color: Qt.rgba(0, 0, 0, 0.82)
        border.width: root.isCritical ? 2 : 1
        border.color: root.isCritical
            ? root.accentColor
            : Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g,
                      Theme.Tokens.chalk.b, 0.06)
        Behavior on border.color { ColorAnimation { duration: 180 } }
    }

    // Critical pulse layer (subtle red wash)
    Rectangle {
        anchors.fill: parent
        radius: 10
        color: Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.12)
        visible: root.isCritical
        SequentialAnimation on opacity {
            running: root.isCritical
            loops: Animation.Infinite
            NumberAnimation { from: 0.35; to: 0.9; duration: 500; easing.type: Easing.InOutSine }
            NumberAnimation { from: 0.9; to: 0.35; duration: 500; easing.type: Easing.InOutSine }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 2

        // Headline — big, bold, accent-coloured
        Text {
            text: root.hasContent ? root.headline : "\u2014"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(26 * root.fontScale)
            font.weight: Font.Black
            font.letterSpacing: 1.5
            color: root.hasContent ? root.accentColor : Theme.Tokens.steel
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            opacity: root.hasContent ? 1.0 : 0.35
            Behavior on color { ColorAnimation { duration: 180 } }
        }

        // Sub-text — fuel load and tire action
        Text {
            text: root.sub
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(11 * root.fontScale)
            font.weight: Font.DemiBold
            font.letterSpacing: 0.8
            color: Theme.Tokens.chalk
            opacity: 0.82
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            visible: root.sub.length > 0
        }
    }
}
