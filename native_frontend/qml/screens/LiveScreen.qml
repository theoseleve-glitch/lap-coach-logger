import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LapCoachDesktop

Item {
    property var state: ({})

    SplitView {
        anchors.fill: parent
        spacing: Theme.space4

        SurfacePane {
            SplitView.fillWidth: true
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.space5
                spacing: Theme.space5

                SectionHeader { title: "Live Telemetry" }
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
                    color: Theme.canvasBg
                    Canvas {
                        anchors.fill: parent
                        onPaint: {
                            const ctx = getContext("2d")
                            ctx.clearRect(0, 0, width, height)
                            ctx.strokeStyle = "#2d3744"
                            ctx.lineWidth = 1
                            for (let i = 0; i < 5; ++i) {
                                ctx.beginPath()
                                ctx.moveTo(0, height * (i + 1) / 6)
                                ctx.lineTo(width, height * (i + 1) / 6)
                                ctx.stroke()
                            }
                            ctx.strokeStyle = Theme.accent
                            ctx.lineWidth = 2
                            ctx.beginPath()
                            for (let x = 0; x < width; x += 24) {
                                const y = height * 0.5 + Math.sin((x / width) * 9 + Date.now() / 700) * height * 0.17
                                if (x === 0)
                                    ctx.moveTo(x, y)
                                else
                                    ctx.lineTo(x, y)
                            }
                            ctx.stroke()
                        }
                    }
                }
            }
        }

        SurfacePane {
            SplitView.preferredWidth: 320
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.space5
                spacing: Theme.space4
                SectionHeader { title: "Diagnostics" }
                Repeater {
                    model: state.health || []
                    delegate: RowLayout {
                        required property string label
                        required property string value
                        Layout.fillWidth: true
                        Text { text: label; color: Theme.textMuted; font.pixelSize: Theme.fontMeta }
                        Item { Layout.fillWidth: true }
                        Text { text: value; color: Theme.text; font.pixelSize: Theme.fontBody }
                    }
                }
            }
        }
    }
}
