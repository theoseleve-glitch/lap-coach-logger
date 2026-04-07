import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme

RowLayout {
    id: root

    property var model: []
    property string currentSection: ""

    signal sectionRequested(string sectionId)

    spacing: Theme.Tokens.xs

    Repeater {
        model: root.model

        Rectangle {
            id: chip

            required property var modelData
            required property int index

            readonly property bool active: root.currentSection === modelData.id

            implicitWidth: chipLabel.implicitWidth + 32
            implicitHeight: chipLabel.implicitHeight + 16
            radius: Theme.Tokens.radiusMd
            color: active
                   ? Qt.rgba(Theme.Tokens.pitOrange.r,
                             Theme.Tokens.pitOrange.g,
                             Theme.Tokens.pitOrange.b, 0.12)
                   : Theme.Tokens.subtle(Theme.Tokens.chalk)
            border.width: 1
            border.color: active
                          ? Qt.rgba(Theme.Tokens.pitOrange.r,
                                    Theme.Tokens.pitOrange.g,
                                    Theme.Tokens.pitOrange.b, 0.20)
                          : Theme.Tokens.subtle(Theme.Tokens.chalk)

            Behavior on color {
                ColorAnimation { duration: Theme.Motion.focusDuration }
            }
            Behavior on border.color {
                ColorAnimation { duration: Theme.Motion.focusDuration }
            }

            Text {
                id: chipLabel
                anchors.centerIn: parent
                text: chip.modelData.label
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 11
                font.weight: Font.Bold
                font.letterSpacing: 0.5
                color: chip.active ? Theme.Tokens.chalk : Theme.Tokens.steel

                Behavior on color {
                    ColorAnimation { duration: Theme.Motion.focusDuration }
                }
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.sectionRequested(chip.modelData.id)
            }
        }
    }
}
