import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  ChatWidget — streaming chat display (280x200).
    Dark scrolling text area with username colors for live stream chat.
    Category: streaming — uses racingPurple accent.                    */
Rectangle {
    id: root
    width: 280
    height: 200
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    // [{user: string, text: string, color: string, timestamp: string}]
    property var messages: [
        { user: "Driver42", text: "Great lap!", color: "#22C55E", timestamp: "14:01" },
        { user: "Spotter_A", text: "Car left", color: "#FACC15", timestamp: "14:02" },
        { user: "RaceControl", text: "Yellow flag S2", color: "#FF2A2A", timestamp: "14:03" }
    ]

    onMessagesChanged: {
        // Auto-scroll to bottom
        chatList.positionViewAtEnd()
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 8
            bottomMargin: 8
            leftMargin: 10
            rightMargin: 10
        }
        spacing: 0

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "CHAT"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            // Streaming badge
            Rectangle {
                implicitWidth: streamLbl.implicitWidth + 8
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
                    id: streamLbl
                    anchors.centerIn: parent
                    text: "STREAM"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    font.weight: Font.Bold
                    color: Theme.Tokens.racingPurple
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root.messages.length + " msg"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                color: Theme.Tokens.steel
                opacity: 0.6
            }
        }

        // ── Separator ──────────────────────────────────────────────
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

        // ── Chat messages list ─────────────────────────────────────
        ListView {
            id: chatList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 3
            model: root.messages.length

            delegate: RowLayout {
                required property int index
                width: chatList.width
                spacing: 4

                property var msg: root.messages[index] || {}

                // Timestamp
                Text {
                    text: msg.timestamp || ""
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    color: Qt.rgba(Theme.Tokens.steel.r,
                                   Theme.Tokens.steel.g,
                                   Theme.Tokens.steel.b, 0.50)
                    Layout.alignment: Qt.AlignTop
                    Layout.preferredWidth: 28
                }

                // Username
                Text {
                    text: (msg.user || "???") + ":"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 10
                    font.weight: Font.Bold
                    color: msg.color || Theme.Tokens.racingPurple
                    Layout.alignment: Qt.AlignTop
                }

                // Message text
                Text {
                    text: msg.text || ""
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 10
                    color: Theme.Tokens.chalk
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                }
            }
        }
    }
}
