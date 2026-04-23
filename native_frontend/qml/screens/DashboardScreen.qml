import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Basic
import LapCoachDesktop

Item {
    property var state: ({})

    SplitView {
        anchors.fill: parent
        spacing: Theme.space4

        SurfacePane {
            SplitView.preferredWidth: 300
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.space5
                spacing: Theme.space5

                SectionHeader { title: "Operations" }
                Repeater {
                    model: Object.keys(state.operations || {})
                    delegate: RowLayout {
                        required property string modelData
                        Layout.fillWidth: true
                        Text { text: modelData; color: Theme.textMuted; font.pixelSize: Theme.fontMeta }
                        Item { Layout.fillWidth: true }
                        Text { text: state.operations[modelData]; color: Theme.text; font.pixelSize: Theme.fontBody }
                    }
                }
            }
        }

        SurfacePane {
            SplitView.fillWidth: true
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.space5
                spacing: Theme.space5

                SectionHeader { title: "Current Run" }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 4
                    columnSpacing: Theme.space4
                    rowSpacing: Theme.space4

                    Repeater {
                        model: state.metrics || []
                        delegate: MetricCell {
                            required property string label
                            required property string value
                            required property string tone
                            Layout.fillWidth: true
                        }
                    }
                }

                SurfacePane {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Theme.paneAltBg
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.space5
                        spacing: Theme.space4
                        SectionHeader { title: "Coaching" }
                        Repeater {
                            model: state.coaching || []
                            delegate: ColumnLayout {
                                required property string label
                                required property string message
                                Layout.fillWidth: true
                                spacing: 2
                                Text { text: label; color: Theme.text; font.pixelSize: Theme.fontBody; font.weight: Font.DemiBold }
                                Text { text: message; color: Theme.textMuted; font.pixelSize: Theme.fontBody; wrapMode: Text.Wrap }
                            }
                        }
                    }
                }
            }
        }
    }
}
