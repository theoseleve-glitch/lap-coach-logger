import QtQuick
import QtQuick.Layouts
import LapCoachDesktop

SurfacePane {
    id: root
    property string title: ""
    property string subtitle: ""
    property string mode: ""
    property string layoutName: ""

    color: Theme.canvasBg

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.space5
        spacing: Theme.space4

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.space4

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: root.title
                    color: Theme.text
                    font.pixelSize: 20
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }

                Text {
                    text: root.subtitle
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontBody
                    elide: Text.ElideRight
                }
            }

            StatusBadge {
                label: root.mode
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.radiusMd
            color: Theme.canvasFrame
            border.width: 1
            border.color: Theme.borderStrong

            Rectangle {
                anchors.fill: parent
                anchors.margins: Theme.space6
                color: "#0b0f13"
                border.width: 1
                border.color: Theme.border
                radius: Theme.radiusSm

                Repeater {
                    model: 10
                    delegate: Rectangle {
                        width: parent.width
                        height: 1
                        y: (index + 1) * parent.height / 11
                        color: "#17202a"
                        opacity: 0.5
                    }
                }

                Repeater {
                    model: 14
                    delegate: Rectangle {
                        width: 1
                        height: parent.height
                        x: (index + 1) * parent.width / 15
                        color: "#17202a"
                        opacity: 0.5
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: Theme.space6
                    color: "transparent"
                    border.width: 1
                    border.color: Theme.warning
                    radius: Theme.radiusXs
                    opacity: 0.35
                }

                Rectangle {
                    width: parent.width * 0.24
                    height: parent.height * 0.14
                    x: parent.width * 0.69
                    y: parent.height * 0.32
                    radius: Theme.radiusXs
                    color: "#d9dbe0"
                    opacity: 0.82
                    border.width: 2
                    border.color: Theme.accent
                }

                Rectangle {
                    width: 12
                    height: 12
                    x: parent.width * 0.69 + parent.width * 0.24 - 8
                    y: parent.height * 0.32 + parent.height * 0.14 - 8
                    radius: 2
                    color: Theme.accent
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.space6

            Text { text: "Layout"; color: Theme.textMuted; font.pixelSize: Theme.fontMeta }
            Text { text: root.layoutName; color: Theme.text; font.pixelSize: Theme.fontBody }
            Text { text: "Anchor"; color: Theme.textMuted; font.pixelSize: Theme.fontMeta }
            Text { text: "Right"; color: Theme.text; font.pixelSize: Theme.fontBody }
            Item { Layout.fillWidth: true }
            Text { text: "Preview mode"; color: Theme.textMuted; font.pixelSize: Theme.fontMeta }
            Text { text: root.mode; color: Theme.text; font.pixelSize: Theme.fontBody }
        }
    }
}
