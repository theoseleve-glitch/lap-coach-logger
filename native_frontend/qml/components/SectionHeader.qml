import QtQuick
import LapCoachDesktop

Item {
    id: root
    property string title: ""
    property string detail: ""
    implicitHeight: 26

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: Theme.border
    }

    Text {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        text: root.title
        color: Theme.text
        font.pixelSize: Theme.fontSection
        font.weight: Font.DemiBold
    }

    Text {
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        text: root.detail
        color: Theme.textMuted
        font.pixelSize: Theme.fontMeta
        visible: text.length > 0
    }
}
