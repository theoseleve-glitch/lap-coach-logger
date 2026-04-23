import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  StrategyStatusWidget — always-on compact strategy banner (400 x 40).

    One line, monospaced, color-coded by severity:
      - "ok"       → steel (calm, blends in)
      - "advisory" → marshal yellow (noticed but not alarming)
      - "critical" → safety red (impossible to miss)

    Renders the line verbatim from Python (no formatting logic here) so
    the content rules stay testable. Degraded state (empty line) shows
    a muted placeholder rather than a blank widget.                     */
Rectangle {
    id: root

    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 400
    height: 40
    color: "transparent"

    // -- public API -------------------------------------------------------
    property string line: ""
    property string severity: "ok"

    // -- derived ----------------------------------------------------------
    readonly property bool hasContent: line.length > 0
    readonly property color textColor: {
        switch (severity) {
        case "critical": return Theme.Tokens.safetyRed
        case "advisory": return Theme.Tokens.marshalYellow
        default:         return Theme.Tokens.chalk
        }
    }

    // Background panel
    Rectangle {
        anchors.fill: parent
        radius: 8
        color: Qt.rgba(0, 0, 0, 0.78)
        border.width: 1
        border.color: root.severity === "critical"
            ? Qt.rgba(Theme.Tokens.safetyRed.r, Theme.Tokens.safetyRed.g,
                      Theme.Tokens.safetyRed.b, 0.4)
            : Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g,
                      Theme.Tokens.chalk.b, 0.06)
        Behavior on border.color { ColorAnimation { duration: 200 } }
    }

    // Severity dot (left indicator)
    Rectangle {
        id: severityDot
        width: 6
        height: 6
        radius: 3
        anchors {
            left: parent.left
            leftMargin: 12
            verticalCenter: parent.verticalCenter
        }
        color: root.textColor
        Behavior on color { ColorAnimation { duration: 200 } }
    }

    // Status line — monospaced so numbers don't jitter
    Text {
        anchors {
            left: severityDot.right
            leftMargin: 10
            right: parent.right
            rightMargin: 12
            verticalCenter: parent.verticalCenter
        }
        text: root.hasContent ? root.line : "No strategy data"
        font.family: Theme.Typography.monoFamily
        font.pixelSize: Math.round(13 * root.fontScale)
        font.weight: Font.DemiBold
        font.letterSpacing: 0.3
        color: root.textColor
        opacity: root.hasContent ? 1.0 : 0.4
        elide: Text.ElideRight
        Behavior on color { ColorAnimation { duration: 200 } }
    }
}
