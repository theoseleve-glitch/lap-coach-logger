import QtQuick
import QtQuick.Layouts
import LapCoachDesktop

SurfacePane {
    id: root
    property alias title: header.title
    default property alias contentData: contentColumn.data
    color: Theme.paneAltBg

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.space5
        spacing: Theme.space4

        SectionHeader {
            id: header
            Layout.fillWidth: true
        }

        ColumnLayout {
            id: contentColumn
            Layout.fillWidth: true
            spacing: Theme.space3
        }
    }
}
