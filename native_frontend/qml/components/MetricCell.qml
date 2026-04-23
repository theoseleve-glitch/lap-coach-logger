import QtQuick
import QtQuick.Layouts
import LapCoachDesktop

SurfacePane {
    id: root
    property string label: ""
    property string value: ""
    property string tone: "neutral"
    color: Theme.paneAltBg

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.space4
        spacing: 2

        Text {
            text: root.label
            color: Theme.textMuted
            font.pixelSize: Theme.fontMeta
        }

        Text {
            text: root.value
            color: root.tone === "accent" ? Theme.warning : Theme.text
            font.pixelSize: 20
            font.weight: Font.DemiBold
        }
    }
}
