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

                SectionHeader { title: "Logs"; detail: modelRef ? modelRef.count + " events" : "" }
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: modelRef
                    spacing: 1
                    delegate: Rectangle {
                        required property string time
                        required property string severity
                        required property string subsystem
                        required property string module
                        required property string message
                        width: ListView.view.width
                        height: 54
                        color: index % 2 === 0 ? Theme.paneAltBg : Theme.paneBg

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.space4
                            spacing: Theme.space5
                            Text { text: time; color: Theme.textMuted; font.pixelSize: Theme.fontMeta; Layout.preferredWidth: 70 }
                            Text { text: severity; color: severity === "WARN" ? Theme.warning : Theme.text; font.pixelSize: Theme.fontMeta; Layout.preferredWidth: 48 }
                            Text { text: subsystem; color: Theme.text; font.pixelSize: Theme.fontBody; Layout.preferredWidth: 90 }
                            Text { text: module; color: Theme.textMuted; font.pixelSize: Theme.fontMeta; Layout.preferredWidth: 280; elide: Text.ElideRight }
                            Text { text: message; color: Theme.text; font.pixelSize: Theme.fontBody; Layout.fillWidth: true; elide: Text.ElideRight }
                        }
                    }
                }
            }
        }
    }
}
