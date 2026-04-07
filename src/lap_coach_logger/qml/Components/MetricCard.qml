import QtQuick
import "../Theme" as Theme

Rectangle {
    id: root

    property string label: ""
    property string value: ""
    property string subtitle: ""

    implicitWidth: 180
    implicitHeight: contentColumn.implicitHeight + Theme.Tokens.xl * 2
    radius: Theme.Tokens.radiusLg
    color: Theme.Tokens.surface
    border.width: 1
    border.color: hovered ? Theme.Tokens.medium(Theme.Tokens.chalk)
                          : Theme.Tokens.subtle(Theme.Tokens.chalk)

    property bool hovered: false

    Behavior on border.color {
        ColorAnimation { duration: Theme.Motion.focusDuration }
    }

    MouseArea {
        id: hoverArea
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        onContainsMouseChanged: root.hovered = containsMouse
    }

    Column {
        id: contentColumn
        anchors {
            left: parent.left
            right: parent.right
            top: parent.top
            margins: Theme.Tokens.xl
        }
        spacing: Theme.Tokens.xs

        // Label — micro style
        Text {
            text: root.label.toUpperCase()
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.microSize
            font.weight: Theme.Typography.microWeight
            font.letterSpacing: Theme.Typography.microSpacing
            color: Theme.Tokens.steel
        }

        // Value — large mono number
        Text {
            text: root.value
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.displaySize
            font.weight: Font.Bold
            color: Theme.Tokens.chalk
        }

        // Subtitle — caption style (only if non-empty)
        Text {
            visible: root.subtitle !== ""
            text: root.subtitle
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: Theme.Typography.captionSize
            color: Theme.Tokens.steel
        }
    }
}
