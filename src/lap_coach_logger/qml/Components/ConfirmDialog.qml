import QtQuick
import "../Theme" as Theme

Item {
    id: root

    property string title: ""
    property string message: ""
    property bool isOpen: false

    signal confirmed()
    signal cancelled()

    anchors.fill: parent
    visible: root.isOpen

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
            onClicked: root.cancelled()
        }
    }

    // Dialog box
    Rectangle {
        id: dialogBox
        width: Math.min(400, parent.width - Theme.Tokens.xxl * 2)
        anchors.centerIn: parent
        radius: Theme.Tokens.radiusLg
        color: Theme.Tokens.surface
        border.width: 1
        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

        implicitHeight: dialogColumn.implicitHeight + Theme.Tokens.xl * 2

        scale: root.isOpen ? 1.0 : Theme.Motion.dialogStartScale
        opacity: root.isOpen ? 1.0 : 0.0

        Behavior on scale {
            NumberAnimation {
                duration: Theme.Motion.dialogDuration
                easing.type: Easing.OutBack
            }
        }
        Behavior on opacity {
            NumberAnimation { duration: Theme.Motion.dialogDuration }
        }

        Column {
            id: dialogColumn
            anchors {
                left: parent.left
                right: parent.right
                top: parent.top
                margins: Theme.Tokens.xl
            }
            spacing: Theme.Tokens.lg

            // Title
            Text {
                text: root.title
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.headingSize
                font.weight: Theme.Typography.headingWeight
                color: Theme.Tokens.chalk
                width: parent.width
                wrapMode: Text.WordWrap
            }

            // Message
            Text {
                text: root.message
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.bodySize
                color: Theme.Tokens.steel
                width: parent.width
                wrapMode: Text.WordWrap
            }

            // Button row
            Row {
                anchors.right: parent.right
                spacing: Theme.Tokens.sm
                topPadding: Theme.Tokens.sm

                // Cancel button
                Rectangle {
                    width: cancelText.implicitWidth + Theme.Tokens.xl * 2
                    height: 36
                    radius: Theme.Tokens.radiusMd
                    color: cancelArea.containsMouse
                           ? Theme.Tokens.subtle(Theme.Tokens.chalk)
                           : "transparent"

                    Text {
                        id: cancelText
                        anchors.centerIn: parent
                        text: "Cancel"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.bodySize
                        font.weight: Font.DemiBold
                        color: Theme.Tokens.steel
                    }

                    MouseArea {
                        id: cancelArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.cancelled()
                    }
                }

                // Confirm button
                Rectangle {
                    width: confirmText.implicitWidth + Theme.Tokens.xl * 2
                    height: 36
                    radius: Theme.Tokens.radiusMd
                    color: confirmArea.containsMouse
                           ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.25)
                           : Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.18)
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.25)

                    Text {
                        id: confirmText
                        anchors.centerIn: parent
                        text: "Confirm"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.bodySize
                        font.weight: Font.DemiBold
                        color: Theme.Tokens.chalk
                    }

                    MouseArea {
                        id: confirmArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.confirmed()
                    }
                }
            }
        }
    }
}
