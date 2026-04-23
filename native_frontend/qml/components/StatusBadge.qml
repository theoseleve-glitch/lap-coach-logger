import QtQuick
import LapCoachDesktop

Rectangle {
    id: root
    property string tone: "neutral"
    property string label: ""
    implicitHeight: 20
    implicitWidth: textItem.implicitWidth + 12
    radius: Theme.radiusXs
    color: tone === "success" ? "#12331f" :
           tone === "warning" ? "#322715" :
           tone === "error" ? "#3c1616" :
           "#141a21"
    border.width: 1
    border.color: tone === "success" ? Theme.success :
                  tone === "warning" ? Theme.warning :
                  tone === "error" ? Theme.error :
                  Theme.border

    Text {
        id: textItem
        anchors.centerIn: parent
        text: root.label
        color: Theme.text
        font.pixelSize: Theme.fontMicro
        font.weight: Font.DemiBold
    }
}
