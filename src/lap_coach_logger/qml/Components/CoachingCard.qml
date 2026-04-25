import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme

// T094: Renders ONE coaching insight at a time from the rules
// engine via T091's CoachingCardViewModel (exposed to QML as
// ``coachingCardVM``). Visibility tracks ``has_insight`` so the
// widget disappears cleanly when nothing's shown.
//
// T095 will add fade in/out, T096 audio cue, T097 dismiss
// button, T098 flag-as-wrong button. T094 ships the static
// layout only.

Rectangle {
    id: root

    // -- VM contract ----------------------------------------------------------
    // The HUD shell injects ``coachingCardVM`` into this widget's scope.

    visible: coachingCardVM.has_insight

    implicitWidth: 320
    implicitHeight: contentColumn.implicitHeight + Theme.Tokens.xl * 2
    radius: Theme.Tokens.radiusLg
    color: Theme.Tokens.surface
    border.width: 1
    border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.4)

    Column {
        id: contentColumn
        anchors {
            left: parent.left
            right: parent.right
            top: parent.top
            margins: Theme.Tokens.xl
        }
        spacing: Theme.Tokens.sm

        // Category / rule-id pill — micro style; gives the user
        // a quick "what's this about?" handle.
        Text {
            id: ruleIdPill
            text: (coachingCardVM.insight.rule_id || "").toUpperCase()
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.microSize
            font.weight: Theme.Typography.microWeight
            font.letterSpacing: Theme.Typography.microSpacing
            color: Theme.Tokens.pitOrange
        }

        // Title — generic name for this coaching point. Used
        // verbatim, not skill-level resolved (that's the body's
        // job per T093).
        Text {
            id: titleText
            text: coachingCardVM.insight.title || ""
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: 16
            font.weight: Font.Bold
            color: Theme.Tokens.chalk
            wrapMode: Text.Wrap
            width: parent.width
        }

        // Body — T093's skill-level resolved text. Fallback chain
        // (skill_levels[level] → title → "") is in the VM, so
        // QML's ``|| "—"`` only kicks in for the pathological
        // empty case.
        Text {
            id: bodyText
            text: coachingCardVM.insight.text || "—"
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: 13
            color: Theme.Tokens.steel
            wrapMode: Text.Wrap
            width: parent.width
        }
    }
}
