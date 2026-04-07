import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  GarageCoverWidget — BRB / intermission screen for streams (320x180).
    "IN THE GARAGE" with subtitle and optional branding.
    Category: streaming — uses racingPurple accent.                       */
Rectangle {
    id: root
    width: 320
    height: 180
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property string message: "IN THE GARAGE"
    property string subMessage: ""
    property bool   showLogo: true

    // ── content ─────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        radius: 10
        color: Qt.rgba(0, 0, 0, 0.75)
        border.width: 1
        border.color: Qt.rgba(Theme.Tokens.racingPurple.r,
                              Theme.Tokens.racingPurple.g,
                              Theme.Tokens.racingPurple.b, 0.20)

        // Subtle breathing opacity on the whole card
        SequentialAnimation on opacity {
            loops: Animation.Infinite
            NumberAnimation { from: 1.0; to: 0.88; duration: 3000; easing.type: Easing.InOutSine }
            NumberAnimation { from: 0.88; to: 1.0; duration: 3000; easing.type: Easing.InOutSine }
        }

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 10

            // ── Logo placeholder ───────────────────────────────────
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                visible: root.showLogo
                width: 40; height: 40; radius: 20
                color: Qt.rgba(Theme.Tokens.racingPurple.r,
                               Theme.Tokens.racingPurple.g,
                               Theme.Tokens.racingPurple.b, 0.12)
                border.width: 1
                border.color: Qt.rgba(Theme.Tokens.racingPurple.r,
                                      Theme.Tokens.racingPurple.g,
                                      Theme.Tokens.racingPurple.b, 0.25)

                Text {
                    anchors.centerIn: parent
                    text: "LC"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    color: Theme.Tokens.racingPurple
                }
            }

            // ── Main message ───────────────────────────────────────
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: root.message
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 22
                font.weight: Font.Bold
                font.letterSpacing: 2.0
                color: Theme.Tokens.chalk
            }

            // ── Sub-message ────────────────────────────────────────
            Text {
                Layout.alignment: Qt.AlignHCenter
                visible: root.subMessage.length > 0
                text: root.subMessage
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 11
                color: Theme.Tokens.steel
                opacity: 0.7
            }

            // ── Racing purple accent line ──────────────────────────
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: 60; height: 2; radius: 1
                color: Theme.Tokens.racingPurple
                opacity: 0.5
            }

            // ── Streaming dot indicator ────────────────────────────
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 6

                Rectangle {
                    width: 5; height: 5; radius: 2.5
                    color: Theme.Tokens.racingPurple

                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.3; duration: 1000 }
                        NumberAnimation { from: 0.3; to: 1.0; duration: 1000 }
                    }
                }

                Text {
                    text: "BE RIGHT BACK"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.Bold
                    font.letterSpacing: 1.0
                    color: Theme.Tokens.racingPurple
                    opacity: 0.6
                }
            }
        }
    }
}
