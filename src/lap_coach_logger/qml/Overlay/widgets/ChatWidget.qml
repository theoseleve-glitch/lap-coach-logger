import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  ChatWidget — streaming chat display (280 x 200).
    Dark scrolling text area with username colors for live stream chat.
    Category: streaming — uses racingPurple accent.

    Features: STREAM badge, auto-scroll to bottom with smooth animation,
    empty state, null-safe messages list, dimmed timestamps.              */
Rectangle {
    id: root
    width: 280
    height: 200
    color: "transparent"

    // ── Public API ──────────────────────────────────────────────────
    // [{user: string, text: string, color: string, timestamp: string}]
    property var messages: []

    // ── Null-safe helpers ───────────────────────────────────────────
    readonly property var safeMessages: Array.isArray(root.messages) ? root.messages : []
    readonly property int messageCount: root.safeMessages.length

    function safeMsg(idx) {
        if (idx < 0 || idx >= root.safeMessages.length)
            return { user: "", text: "", color: "", timestamp: "" }
        return root.safeMessages[idx] || { user: "", text: "", color: "", timestamp: "" }
    }

    onMessagesChanged: {
        // Smooth auto-scroll to bottom after model updates
        if (root.messageCount > 0) {
            scrollTimer.restart()
        }
    }

    // Slight delay so the ListView has time to lay out new delegate
    Timer {
        id: scrollTimer
        interval: 30
        onTriggered: {
            chatList.positionViewAtEnd()
        }
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: Theme.Tokens.sm
            bottomMargin: Theme.Tokens.sm
            leftMargin: Theme.Tokens.sm + 2
            rightMargin: Theme.Tokens.sm + 2
        }
        spacing: 0

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.Tokens.sm - 2

            Text {
                text: "CHAT"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize - 1
                font.weight: Theme.Typography.microWeight
                font.letterSpacing: Theme.Typography.microSpacing - 0.3
                color: Theme.Tokens.steel
            }

            // STREAM badge
            Rectangle {
                implicitWidth: streamLbl.implicitWidth + Theme.Tokens.sm
                implicitHeight: 14
                radius: 3
                color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.15)
                border.width: 1
                border.color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.30)

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
                text: root.messageCount + " msg"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                color: Theme.Tokens.steel
                opacity: 0.6
            }
        }

        // ── Separator ──────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.Tokens.sm - 2
            Rectangle {
                anchors.centerIn: parent
                width: parent.width; height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5; color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.12) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // ── Empty state ────────────────────────────────────────────
        Text {
            visible: root.messageCount === 0
            text: "No messages"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.captionSize
            color: Theme.Tokens.steel
            opacity: 0.5
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: Theme.Tokens.xxl
        }

        // ── Chat messages list ─────────────────────────────────────
        ListView {
            id: chatList
            visible: root.messageCount > 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 3
            model: root.messageCount

            // Smooth scroll when content changes
            Behavior on contentY {
                NumberAnimation { duration: Theme.Motion.hoverDuration; easing.type: Easing.OutCubic }
            }

            // Fade-in for new messages
            add: Transition {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.Motion.hoverDuration }
            }

            delegate: RowLayout {
                required property int index
                width: chatList.width
                spacing: Theme.Tokens.xs

                property var msg: root.safeMsg(index)

                // Timestamp (dimmed)
                Text {
                    text: msg.timestamp || ""
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    color: Theme.Tokens.steel
                    opacity: 0.4
                    Layout.alignment: Qt.AlignTop
                    Layout.preferredWidth: 28
                }

                // Username (colored)
                Text {
                    text: (msg.user || "???") + ":"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Theme.Typography.microSize
                    font.weight: Font.Bold
                    color: msg.color || Theme.Tokens.racingPurple
                    Layout.alignment: Qt.AlignTop
                }

                // Message text
                Text {
                    text: msg.text || ""
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Theme.Typography.microSize
                    color: Theme.Tokens.chalk
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                }
            }
        }
    }
}
