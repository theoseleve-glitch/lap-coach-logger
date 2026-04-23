import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LapCoachDesktop

Item {
    property var state: ({})

    SurfacePane {
        anchors.fill: parent
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Theme.space5
            spacing: Theme.space5

            SectionHeader { title: state.title || "Review"; detail: state.status || "" }

            Text {
                text: state.summary || ""
                color: Theme.text
                font.pixelSize: Theme.fontBody
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }

            InspectorGroup {
                Layout.fillWidth: true
                title: "Warnings"
                Repeater {
                    model: state.warnings || []
                    delegate: Text {
                        required property string modelData
                        text: "• " + modelData
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontBody
                        wrapMode: Text.Wrap
                    }
                }
            }
        }
    }
}
