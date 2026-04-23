import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LapCoachDesktop

Item {
    property var modelRef

    SplitView {
        anchors.fill: parent
        spacing: Theme.space4

        SurfacePane {
            SplitView.fillWidth: true
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.space5
                spacing: Theme.space4
                SectionHeader { title: "Session Archive" }

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: modelRef
                    spacing: 1
                    delegate: Rectangle {
                        required property string date
                        required property string sim
                        required property string track
                        required property string car
                        required property string duration
                        required property string laps
                        required property string quality
                        width: ListView.view.width
                        height: 56
                        color: index % 2 === 0 ? Theme.paneAltBg : Theme.paneBg

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.space4
                            spacing: Theme.space5
                            Text { text: date; color: Theme.textMuted; font.pixelSize: Theme.fontMeta; Layout.preferredWidth: 130 }
                            Text { text: sim; color: Theme.text; font.pixelSize: Theme.fontBody; Layout.preferredWidth: 52 }
                            Text { text: track; color: Theme.text; font.pixelSize: Theme.fontBody; Layout.preferredWidth: 180; elide: Text.ElideRight }
                            Text { text: car; color: Theme.textMuted; font.pixelSize: Theme.fontMeta; Layout.fillWidth: true; elide: Text.ElideRight }
                            Text { text: duration; color: Theme.text; font.pixelSize: Theme.fontBody; Layout.preferredWidth: 52 }
                            Text { text: laps; color: Theme.text; font.pixelSize: Theme.fontBody; Layout.preferredWidth: 36 }
                            Text { text: quality; color: Theme.warning; font.pixelSize: Theme.fontMeta; Layout.preferredWidth: 64 }
                        }
                    }
                }
            }
        }
    }
}
