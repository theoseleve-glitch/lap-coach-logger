import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme

Rectangle {
    id: root

    property alias text: input.text
    property string placeholder: "Search tracks, sims..."

    signal searchTextChanged(string searchText)

    implicitWidth: Math.max(200, searchRow.implicitWidth + 28)
    implicitHeight: searchRow.implicitHeight + 16
    radius: Theme.Tokens.radiusMd
    color: Theme.Tokens.raised
    border.width: 1
    border.color: input.activeFocus
                  ? Theme.Tokens.pitOrange
                  : Theme.Tokens.subtle(Theme.Tokens.chalk)

    Behavior on border.color {
        ColorAnimation { duration: Theme.Motion.focusDuration }
    }

    RowLayout {
        id: searchRow
        anchors {
            fill: parent
            leftMargin: 14
            rightMargin: 14
            topMargin: 8
            bottomMargin: 8
        }
        spacing: Theme.Tokens.sm

        // Search icon
        Text {
            text: "\u2315"
            font.pixelSize: 14
            color: "#646464"
            Layout.alignment: Qt.AlignVCenter
        }

        // Input field with placeholder
        Item {
            Layout.fillWidth: true
            implicitHeight: input.implicitHeight

            TextInput {
                id: input
                anchors.fill: parent
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.captionSize
                color: Theme.Tokens.chalk
                clip: true
                selectByMouse: true

                onTextChanged: root.searchTextChanged(text)
            }

            // Placeholder text
            Text {
                anchors.fill: parent
                visible: input.text.length === 0 && !input.activeFocus
                text: root.placeholder
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.captionSize
                color: "#646464"
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
