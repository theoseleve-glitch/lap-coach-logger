import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  ChatHighlightWidget — single highlighted chat message for stream (320x80).
    Large text display of a featured message with fade in/out animation.
    Category: streaming — uses racingPurple accent.                           */
Rectangle {
    id: root
    width: 320
    height: 80
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property string user: ""
    property string text_: ""
    property string userColor: Theme.Tokens.racingPurple
    property bool   visible_: false

    // ── fade animation ──────────────────────────────────────────────
    opacity: visible_ ? 1.0 : 0.0
    Behavior on opacity {
        NumberAnimation { duration: 400; easing.type: Easing.InOutQuad }
    }

    // ── content ─────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        radius: 8
        color: Qt.rgba(0, 0, 0, 0.65)
        border.width: 1
        border.color: Qt.rgba(Theme.Tokens.racingPurple.r,
                              Theme.Tokens.racingPurple.g,
                              Theme.Tokens.racingPurple.b, 0.20)

        // Left accent bar
        Rectangle {
            anchors {
                left: parent.left
                top: parent.top
                bottom: parent.bottom
                leftMargin: 1
                topMargin: 12
                bottomMargin: 12
            }
            width: 3
            radius: 1.5
            color: root.userColor || Theme.Tokens.racingPurple
        }

        ColumnLayout {
            anchors {
                fill: parent
                leftMargin: 14
                rightMargin: 12
                topMargin: 10
                bottomMargin: 10
            }
            spacing: 4

            // ── Username row ───────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                // Streaming dot
                Rectangle {
                    width: 5; height: 5; radius: 2.5
                    color: Theme.Tokens.racingPurple

                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.3; duration: 800 }
                        NumberAnimation { from: 0.3; to: 1.0; duration: 800 }
                    }
                }

                Text {
                    text: root.user
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: root.userColor || Theme.Tokens.racingPurple
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: "HIGHLIGHT"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    font.weight: Font.Bold
                    font.letterSpacing: 1.0
                    color: Theme.Tokens.racingPurple
                    opacity: 0.6
                }
            }

            // ── Message text ───────────────────────────────────────
            Text {
                Layout.fillWidth: true
                Layout.fillHeight: true
                text: root.text_
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 14
                font.weight: Font.DemiBold
                color: Theme.Tokens.chalk
                wrapMode: Text.WordWrap
                elide: Text.ElideRight
                maximumLineCount: 2
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
