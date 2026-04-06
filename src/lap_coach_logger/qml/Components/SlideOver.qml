import QtQuick
import "../Theme" as Theme

Item {
    id: root

    property bool isOpen: false

    signal closeRequested()

    default property alias content: contentArea.data

    anchors.fill: parent

    // Block interaction when closed
    visible: dimBg.opacity > 0 || panel.x < parent.width

    // Dim background
    Rectangle {
        id: dimBg
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, Theme.Motion.dimOpacity)
        opacity: root.isOpen ? 1.0 : 0.0

        Behavior on opacity {
            NumberAnimation { duration: Theme.Motion.dimDuration }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: root.closeRequested()
        }
    }

    // Slide panel
    Rectangle {
        id: panel
        width: 420
        height: parent.height
        x: root.isOpen ? parent.width - 420 : parent.width
        color: Theme.Tokens.surface

        border.width: 1
        border.color: Theme.Tokens.medium(Theme.Tokens.chalk)

        // Use different durations/easings for open vs close
        Behavior on x {
            NumberAnimation {
                duration: root.isOpen ? Theme.Motion.slideOverOpenDuration
                                      : Theme.Motion.slideOverCloseDuration
                easing.type: root.isOpen ? Easing.OutQuint : Easing.InQuad
            }
        }

        // Close button
        Rectangle {
            id: closeBtn
            width: 32
            height: 32
            radius: Theme.Tokens.radiusSm
            color: closeBtnArea.containsMouse
                   ? Theme.Tokens.subtle(Theme.Tokens.chalk)
                   : "transparent"
            anchors {
                top: parent.top
                right: parent.right
                topMargin: Theme.Tokens.lg
                rightMargin: Theme.Tokens.lg
            }

            Text {
                anchors.centerIn: parent
                text: "\u2715"
                font.pixelSize: 14
                color: Theme.Tokens.steel
            }

            MouseArea {
                id: closeBtnArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.closeRequested()
            }
        }

        // Header
        Item {
            id: header
            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
            }
            height: 60

            Text {
                anchors {
                    left: parent.left
                    verticalCenter: parent.verticalCenter
                    leftMargin: Theme.Tokens.xl
                }
                text: "Settings"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: 20
                font.weight: Font.Bold
                color: Theme.Tokens.chalk
            }

            // Bottom border
            Rectangle {
                anchors {
                    left: parent.left
                    right: parent.right
                    bottom: parent.bottom
                }
                height: 1
                color: Theme.Tokens.subtle(Theme.Tokens.chalk)
            }
        }

        // Content area for injected children
        Item {
            id: contentArea
            anchors {
                top: header.bottom
                left: parent.left
                right: parent.right
                bottom: parent.bottom
                margins: Theme.Tokens.xl
            }
        }
    }
}
