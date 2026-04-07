import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  PromoCodeAlertWidget — animated promo code display for streams (300x100).
    Shows sponsor name, promo code with copy indicator, and description.
    Category: streaming — uses racingPurple accent.                          */
Rectangle {
    id: root
    width: 300
    height: 100
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property string code: "RACEFAN20"
    property string sponsor: "Sponsor"
    property string description: "20% off racing gear"
    property bool   isActive: true

    // ── fade in/out ─────────────────────────────────────────────────
    opacity: isActive ? 1.0 : 0.0
    Behavior on opacity {
        NumberAnimation { duration: 400; easing.type: Easing.InOutQuad }
    }

    // ── content ─────────────────────────────────────────────────────
    Rectangle {
        id: card
        anchors.fill: parent
        radius: 8
        color: Qt.rgba(0, 0, 0, 0.65)
        border.width: 1
        border.color: Qt.rgba(Theme.Tokens.racingPurple.r,
                              Theme.Tokens.racingPurple.g,
                              Theme.Tokens.racingPurple.b, 0.25)

        // Pulse glow animation on the border
        SequentialAnimation on border.color {
            running: root.isActive
            loops: Animation.Infinite
            ColorAnimation {
                to: Qt.rgba(Theme.Tokens.racingPurple.r,
                            Theme.Tokens.racingPurple.g,
                            Theme.Tokens.racingPurple.b, 0.50)
                duration: 1200
            }
            ColorAnimation {
                to: Qt.rgba(Theme.Tokens.racingPurple.r,
                            Theme.Tokens.racingPurple.g,
                            Theme.Tokens.racingPurple.b, 0.15)
                duration: 1200
            }
        }

        ColumnLayout {
            anchors {
                fill: parent
                topMargin: 8
                bottomMargin: 8
                leftMargin: 12
                rightMargin: 12
            }
            spacing: 4

            // ── Sponsor row ────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: root.sponsor.toUpperCase()
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    font.letterSpacing: 1.2
                    color: Theme.Tokens.steel
                }

                // PROMO badge
                Rectangle {
                    implicitWidth: promoBadge.implicitWidth + 8
                    implicitHeight: 14
                    radius: 3
                    color: Qt.rgba(Theme.Tokens.racingPurple.r,
                                   Theme.Tokens.racingPurple.g,
                                   Theme.Tokens.racingPurple.b, 0.15)
                    border.width: 1
                    border.color: Qt.rgba(Theme.Tokens.racingPurple.r,
                                          Theme.Tokens.racingPurple.g,
                                          Theme.Tokens.racingPurple.b, 0.30)

                    Text {
                        id: promoBadge
                        anchors.centerIn: parent
                        text: "PROMO"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 7
                        font.weight: Font.Bold
                        color: Theme.Tokens.racingPurple
                    }
                }

                Item { Layout.fillWidth: true }

                // Streaming dot
                Rectangle {
                    width: 5; height: 5; radius: 2.5
                    color: Theme.Tokens.racingPurple

                    SequentialAnimation on opacity {
                        running: root.isActive
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.3; duration: 800 }
                        NumberAnimation { from: 0.3; to: 1.0; duration: 800 }
                    }
                }
            }

            // ── Code display ───────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 32
                radius: 6
                color: Qt.rgba(Theme.Tokens.racingPurple.r,
                               Theme.Tokens.racingPurple.g,
                               Theme.Tokens.racingPurple.b, 0.08)
                border.width: 1
                border.color: Qt.rgba(Theme.Tokens.racingPurple.r,
                                      Theme.Tokens.racingPurple.g,
                                      Theme.Tokens.racingPurple.b, 0.12)

                RowLayout {
                    anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                    spacing: 8

                    Text {
                        text: root.code
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 18
                        font.weight: Font.Bold
                        font.letterSpacing: 2.0
                        color: Theme.Tokens.chalk
                        Layout.fillWidth: true

                        // Subtle pulse on the code
                        SequentialAnimation on opacity {
                            running: root.isActive
                            loops: Animation.Infinite
                            NumberAnimation { from: 1.0; to: 0.8; duration: 1500 }
                            NumberAnimation { from: 0.8; to: 1.0; duration: 1500 }
                        }
                    }

                    // Copy indicator
                    Text {
                        text: "COPY"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 8
                        font.weight: Font.Bold
                        font.letterSpacing: 0.8
                        color: Theme.Tokens.racingPurple
                        opacity: 0.6
                    }
                }
            }

            // ── Description ────────────────────────────────────────
            Text {
                Layout.fillWidth: true
                text: root.description
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 10
                color: Theme.Tokens.steel
                elide: Text.ElideRight
                opacity: 0.7
            }
        }
    }
}
