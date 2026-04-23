import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  RaceReminderWidget — unified coaching surface (320 x 64).

    Compact coaching reminder card bound to the policy-governed
    `coachingSurface*` properties on OverlayViewModel. The surface
    policy decides visibility (cooldown, hysteresis, suppression under
    critical alerts), so this widget is pure rendering — no decisions.

    Layout:
      [focus · category]   [freshness dot]
      HEADLINE              (16pt, chalk)
      subline               (12pt, ac green for live / muted for carryover)

    Freshness affects opacity + dot color:
      - live      → full opacity, accent dot
      - carryover → 0.75 opacity, amber dot
      - stale     → hidden (policy hides it anyway; defensive)

    Severity affects headline tint:
      - positive  → acid green (high-confidence)
      - advisory  → marshal yellow (medium)
      - ok        → chalk (low / generic)
      - critical  → safety red (reserved for alerts — not produced today)   */
Rectangle {
    id: root

    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 320
    height: 64
    color: "transparent"

    // -- public API (bound to overlayVM.coachingSurface*) ------------------
    property bool surfaceVisible: false
    property string headline: ""
    property string sub: ""
    property string severity: "ok"
    property string category: ""
    property string focus: ""
    property string freshness: "stale"
    property string confidence: "low"

    // Hide entirely when policy says so — overlay manager respects this.
    visible: surfaceVisible && headline.length > 0

    // -- derived -----------------------------------------------------------
    readonly property bool isLive: freshness === "live"
    readonly property bool isCarryover: freshness === "carryover"
    readonly property color headlineColor: {
        switch (severity) {
        case "critical": return Theme.Tokens.safetyRed
        case "positive": return Theme.Tokens.acidGreen
        case "advisory": return Theme.Tokens.marshalYellow
        default:         return Theme.Tokens.chalk
        }
    }
    readonly property color freshnessColor: {
        if (isLive) return Theme.Tokens.acidGreen
        if (isCarryover) return Theme.Tokens.marshalYellow
        return Theme.Tokens.steel
    }

    // Background panel
    Rectangle {
        anchors.fill: parent
        radius: 10
        color: Qt.rgba(0, 0, 0, 0.82)
        border.width: 1
        border.color: Qt.rgba(root.headlineColor.r, root.headlineColor.g,
                              root.headlineColor.b, 0.25)
        opacity: root.isCarryover ? 0.88 : 1.0
        Behavior on opacity { NumberAnimation { duration: 250 } }
        Behavior on border.color { ColorAnimation { duration: 250 } }
    }

    // Header row — focus + freshness dot
    RowLayout {
        id: header
        anchors {
            top: parent.top
            topMargin: 6
            left: parent.left
            leftMargin: 12
            right: parent.right
            rightMargin: 12
        }
        spacing: 6

        // Focus label ("T5" / "Sector 2")
        Text {
            text: root.focus || root.category.toUpperCase()
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(9 * root.fontScale)
            font.weight: Font.Bold
            font.letterSpacing: 1.2
            color: Theme.Tokens.steel
            Layout.fillWidth: true
            elide: Text.ElideRight
        }

        // Freshness indicator dot — tiny visual cue
        Rectangle {
            width: 6
            height: 6
            radius: 3
            color: root.freshnessColor
            opacity: root.isCarryover ? 0.7 : 1.0
            Behavior on color { ColorAnimation { duration: 250 } }
        }
    }

    // Headline — the main coaching line
    Text {
        id: headlineText
        anchors {
            top: header.bottom
            topMargin: 2
            left: parent.left
            leftMargin: 12
            right: parent.right
            rightMargin: 12
        }
        text: root.headline
        font.family: Theme.Typography.bodyFamily
        font.pixelSize: Math.round(14 * root.fontScale)
        font.weight: Font.DemiBold
        color: root.headlineColor
        opacity: root.isCarryover ? 0.80 : 1.0
        elide: Text.ElideRight
        Behavior on color { ColorAnimation { duration: 250 } }
        Behavior on opacity { NumberAnimation { duration: 250 } }
    }

    // Subline — action hint
    Text {
        anchors {
            top: headlineText.bottom
            topMargin: 1
            left: parent.left
            leftMargin: 12
            right: parent.right
            rightMargin: 12
        }
        visible: root.sub.length > 0
        text: root.sub
        font.family: Theme.Typography.bodyFamily
        font.pixelSize: Math.round(11 * root.fontScale)
        color: Theme.Tokens.steel
        opacity: root.isCarryover ? 0.70 : 0.92
        elide: Text.ElideRight
    }
}
