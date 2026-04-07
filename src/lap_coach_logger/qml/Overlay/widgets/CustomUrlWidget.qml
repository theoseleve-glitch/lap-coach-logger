import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  CustomUrlWidget — browser widget placeholder for streams (300x200).
    Shows a URL label and "CUSTOM CONTENT" placeholder area.
    Category: streaming — uses racingPurple accent.                      */
Rectangle {
    id: root
    width: 300
    height: 200
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property string url: "https://example.com"
    property string label: "Custom Content"

    // ── content ─────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        radius: 8
        color: Qt.rgba(0, 0, 0, 0.55)
        border.width: 1
        border.color: Qt.rgba(Theme.Tokens.racingPurple.r,
                              Theme.Tokens.racingPurple.g,
                              Theme.Tokens.racingPurple.b, 0.15)

        ColumnLayout {
            anchors {
                fill: parent
                topMargin: 8
                bottomMargin: 8
                leftMargin: 10
                rightMargin: 10
            }
            spacing: 0

            // ── Header ─────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "URL"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    font.letterSpacing: 1.2
                    color: Theme.Tokens.steel
                }

                // Streaming badge
                Rectangle {
                    implicitWidth: urlBadge.implicitWidth + 8
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
                        id: urlBadge
                        anchors.centerIn: parent
                        text: "STREAM"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 7
                        font.weight: Font.Bold
                        color: Theme.Tokens.racingPurple
                    }
                }

                Item { Layout.fillWidth: true }
            }

            // ── URL display ────────────────────────────────────────
            Text {
                Layout.fillWidth: true
                text: root.url
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                color: Theme.Tokens.racingPurple
                elide: Text.ElideMiddle
                opacity: 0.7
            }

            // ── Separator ──────────────────────────────────────────
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 6
                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width; height: 1
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 0.5; color: Qt.rgba(Theme.Tokens.racingPurple.r,
                                                                      Theme.Tokens.racingPurple.g,
                                                                      Theme.Tokens.racingPurple.b, 0.12) }
                        GradientStop { position: 1.0; color: "transparent" }
                    }
                }
            }

            // ── Placeholder content area ───────────────────────────
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 6
                color: Qt.rgba(Theme.Tokens.racingPurple.r,
                               Theme.Tokens.racingPurple.g,
                               Theme.Tokens.racingPurple.b, 0.04)
                border.width: 1
                border.color: Qt.rgba(Theme.Tokens.racingPurple.r,
                                      Theme.Tokens.racingPurple.g,
                                      Theme.Tokens.racingPurple.b, 0.08)

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 6

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "CUSTOM CONTENT"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 10
                        font.weight: Font.Bold
                        font.letterSpacing: 1.0
                        color: Theme.Tokens.racingPurple
                        opacity: 0.6
                    }

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: root.label
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: Theme.Tokens.chalk
                    }

                    // Globe icon placeholder
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        width: 24; height: 24; radius: 12
                        color: Qt.rgba(Theme.Tokens.racingPurple.r,
                                       Theme.Tokens.racingPurple.g,
                                       Theme.Tokens.racingPurple.b, 0.10)
                        border.width: 1
                        border.color: Qt.rgba(Theme.Tokens.racingPurple.r,
                                              Theme.Tokens.racingPurple.g,
                                              Theme.Tokens.racingPurple.b, 0.20)

                        Text {
                            anchors.centerIn: parent
                            text: "\u25CB"
                            font.pixelSize: 14
                            color: Theme.Tokens.racingPurple
                            opacity: 0.5
                        }
                    }
                }
            }
        }
    }
}
