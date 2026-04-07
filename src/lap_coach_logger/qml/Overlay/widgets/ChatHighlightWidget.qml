import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  ChatHighlightWidget -- single highlighted chat message for stream (320x80).
    Large text display of a featured message with animated fade + slide.
    Auto-hides after configurable timeout.
    Category: streaming -- uses racingPurple accent.                           */
Rectangle {
    id: root
    width: 320
    height: 80
    color: "transparent"

    // -- public API ----------------------------------------------------------
    property string user: ""
    property string text_: ""
    property string userColor: ""
    property bool   visible_: false
    property int    autoHideMs: 8000          // 0 = no auto-hide

    // -- internal ------------------------------------------------------------
    readonly property color _accent: root.userColor.length > 0
                                     ? root.userColor
                                     : Theme.Tokens.racingPurple
    readonly property string _safeUser: (root.user || "").length > 0
                                        ? root.user : "---"
    readonly property string _safeText: (root.text_ || "").length > 0
                                        ? root.text_ : ""

    // -- fade + slide animation ----------------------------------------------
    opacity: visible_ ? 1.0 : 0.0
    transform: Translate {
        id: slideTransform
        y: visible_ ? 0 : 8
        Behavior on y {
            NumberAnimation { duration: 400; easing.type: Easing.InOutQuad }
        }
    }

    Behavior on opacity {
        NumberAnimation { duration: 400; easing.type: Easing.InOutQuad }
    }

    // -- auto-hide timer -----------------------------------------------------
    Timer {
        id: autoHideTimer
        interval: root.autoHideMs
        running: false
        repeat: false
        onTriggered: root.visible_ = false
    }

    onVisible_Changed: {
        if (visible_ && autoHideMs > 0) {
            autoHideTimer.restart()
        } else {
            autoHideTimer.stop()
        }
    }

    // -- content -------------------------------------------------------------
    Rectangle {
        anchors.fill: parent
        radius: Theme.Tokens.radiusSm
        color: Qt.rgba(0, 0, 0, 0.65)
        border.width: 1
        border.color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.20)

        // Left accent bar
        Rectangle {
            anchors {
                left: parent.left
                top: parent.top
                bottom: parent.bottom
                leftMargin: 1
                topMargin: Theme.Tokens.md
                bottomMargin: Theme.Tokens.md
            }
            width: 3
            radius: 1.5
            color: root._accent
        }

        ColumnLayout {
            anchors {
                fill: parent
                leftMargin: Theme.Tokens.md + 2      // past accent bar
                rightMargin: Theme.Tokens.md
                topMargin: Theme.Tokens.md - 2
                bottomMargin: Theme.Tokens.md - 2
            }
            spacing: Theme.Tokens.xs

            // -- Username row ------------------------------------------------
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.Tokens.xs + 2

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
                    text: root._safeUser
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: root._accent
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

            // -- Message text ------------------------------------------------
            Text {
                Layout.fillWidth: true
                Layout.fillHeight: true
                text: root._safeText
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.bodySize
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
