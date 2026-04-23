import QtQuick
import QtQuick.Controls
import LapCoachDesktop

Button {
    id: root
    property bool emphasis: false
    property bool danger: false
    implicitHeight: Theme.controlHeight
    implicitWidth: Math.max(70, contentItem.implicitWidth + 18)
    padding: 0

    contentItem: Text {
        text: root.text
        color: root.enabled ? Theme.text : Theme.textDim
        font.pixelSize: Theme.fontBody
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: Theme.radiusXs
        color: root.down
               ? (root.emphasis ? "#9f2121" : Theme.paneRaised)
               : root.hovered
                 ? (root.emphasis ? "#d32f2f" : Theme.selection)
                 : (root.emphasis ? Theme.accent : "transparent")
        border.width: 1
        border.color: root.danger ? Theme.error : (root.emphasis ? Theme.accent : Theme.border)
    }
}
