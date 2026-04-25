import QtQuick
import "../Theme" as Theme

// T104: Fallback card that shows when CoachingCard has nothing
// to display — points the user to the webapp for post-session
// analysis (per Q95: deep analysis lives in the webapp).
//
// Visibility inverts CoachingCard's: only one of the two cards
// is visible at any moment. This avoids the dual-shown
// confusion while preserving CoachingCard's T095 fade
// lifecycle.

Rectangle {
    id: root

    // -- VM contract ----------------------------------------------------------
    // The HUD shell injects ``coachingCardVM`` into this widget's scope.

    visible: !coachingCardVM.has_insight

    implicitWidth: 320
    implicitHeight: contentColumn.implicitHeight + Theme.Tokens.xl * 2
    radius: Theme.Tokens.radiusLg
    color: "transparent"
    border.width: 1
    border.color: Theme.Tokens.subtle(Theme.Tokens.steel, 0.4)

    Column {
        id: contentColumn
        anchors {
            left: parent.left
            right: parent.right
            top: parent.top
            margins: Theme.Tokens.xl
        }
        spacing: Theme.Tokens.xs

        // Quiet, muted body — fallback shouldn't compete with
        // active coaching for the user's attention.
        Text {
            text: "Insights available post-session in webapp"
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: 13
            color: Theme.Tokens.steel
            wrapMode: Text.Wrap
            width: parent.width
        }
    }
}
