import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LapCoachDesktop

SurfacePane {
    id: root
    property var modelRef
    signal layoutChosen(string layoutId)

    color: Theme.chromeBg

    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.space4
        spacing: Theme.space4

        Text {
            text: "Layout"
            color: Theme.textMuted
            font.pixelSize: Theme.fontMeta
        }

        Button {
            text: "+ New"
            implicitHeight: Theme.controlHeight
        }

        ListView {
            id: tabsView
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: ListView.Horizontal
            spacing: Theme.space3
            model: root.modelRef
            clip: true

            delegate: Rectangle {
                required property string layoutId
                required property string displayName
                required property bool selected
                required property bool active
                required property bool favorite

                height: Theme.controlHeight
                width: Math.min(Math.max(label.implicitWidth + 24, 88), 220)
                radius: Theme.radiusXs
                color: selected ? Theme.selection : "transparent"
                border.width: 1
                border.color: selected ? Theme.selectionBorder : Theme.border

                Text {
                    id: label
                    anchors.centerIn: parent
                    text: displayName + (active ? "  • Live" : "")
                    color: Theme.text
                    font.pixelSize: Theme.fontBody
                    elide: Text.ElideRight
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: root.layoutChosen(layoutId)
                }
            }
        }
    }
}
