import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LapCoachDesktop

Item {
    property var state: ({})
    property var categoryModel
    property var overlayModel
    property var layoutModel

    ColumnLayout {
        anchors.fill: parent
        spacing: Theme.space4

        SplitView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.space4

            SurfacePane {
                SplitView.preferredWidth: Theme.sidebarWidth
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.space5
                    spacing: Theme.space4

                    TextField {
                        Layout.fillWidth: true
                        implicitHeight: Theme.controlHeight
                        placeholderText: "Search overlays"
                        onTextChanged: appController.setOverlaySearchQuery(text)
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 42
                        orientation: ListView.Horizontal
                        spacing: Theme.space3
                        model: categoryModel
                        delegate: Rectangle {
                            required property string label
                            required property bool selected
                            required property string category
                            width: Math.max(72, chipLabel.implicitWidth + 18)
                            height: Theme.controlHeight
                            radius: Theme.radiusXs
                            color: selected ? Theme.selection : "transparent"
                            border.width: 1
                            border.color: selected ? Theme.selectionBorder : Theme.border
                            Text {
                                id: chipLabel
                                anchors.centerIn: parent
                                text: label
                                color: Theme.text
                                font.pixelSize: Theme.fontBody
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: appController.selectOverlayCategory(category)
                            }
                        }
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: overlayModel
                        spacing: 1
                        delegate: Rectangle {
                            required property string overlayId
                            required property string displayName
                            required property string category
                            required property string compatibility
                            required property string status
                            required property bool selected
                            required property bool active
                            required property bool favorite
                            required property bool locked
                            width: ListView.view.width
                            height: 64
                            color: selected ? Theme.selection : Theme.paneAltBg
                            border.width: 1
                            border.color: selected ? Theme.selectionBorder : "transparent"

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.space4
                                spacing: Theme.space4

                                Rectangle {
                                    Layout.preferredWidth: 4
                                    Layout.fillHeight: true
                                    color: selected ? Theme.accent : "transparent"
                                }

                                Rectangle {
                                    Layout.preferredWidth: 44
                                    Layout.preferredHeight: 44
                                    radius: Theme.radiusXs
                                    color: Theme.paneRaised
                                    border.width: 1
                                    border.color: Theme.border
                                    Text { anchors.centerIn: parent; text: category.length ? category[0] : "?"; color: Theme.text; font.pixelSize: Theme.fontBody; font.weight: Font.DemiBold }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text { text: displayName; color: Theme.text; font.pixelSize: Theme.fontBody; font.weight: Font.DemiBold; elide: Text.ElideRight }
                                    Text { text: compatibility; color: Theme.textMuted; font.pixelSize: Theme.fontMeta; elide: Text.ElideRight }
                                }

                                ColumnLayout {
                                    spacing: 2
                                    Text { text: status; color: active ? Theme.success : locked ? Theme.warning : Theme.textMuted; font.pixelSize: Theme.fontMeta }
                                    Text { text: favorite ? "Fav" : ""; color: Theme.textMuted; font.pixelSize: Theme.fontMeta }
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: appController.selectOverlay(overlayId)
                            }
                        }
                    }
                }
            }

            OverlayCanvas {
                SplitView.fillWidth: true
                title: state.selectedOverlay ? state.selectedOverlay.displayName || "" : ""
                subtitle: state.selectedOverlay ? state.selectedOverlay.shortDescription || "" : ""
                mode: state.selectedOverlay ? state.selectedOverlay.previewMode || "Preview" : "Preview"
                layoutName: state.selection ? state.selection.selectedLayoutId || "" : ""
            }

            SurfacePane {
                SplitView.preferredWidth: Theme.inspectorWidth
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.space5
                    spacing: Theme.space4

                    SectionHeader { title: "Inspector" }

                    Text {
                        text: state.selectedOverlay ? state.selectedOverlay.displayName || "" : "No overlay selected"
                        color: Theme.text
                        font.pixelSize: 18
                        font.weight: Font.DemiBold
                        wrapMode: Text.Wrap
                    }
                    Text {
                        text: state.selectedOverlay ? state.selectedOverlay.shortDescription || "" : ""
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontBody
                        wrapMode: Text.Wrap
                    }

                    Repeater {
                        model: state.selectedOverlay ? state.selectedOverlay.settingsSections || [] : []
                        delegate: InspectorGroup {
                            required property string label
                            required property var fields
                            Layout.fillWidth: true
                            title: label
                            Repeater {
                                model: fields
                                delegate: RowLayout {
                                    required property string fieldKey
                                    required property string label
                                    required property string kind
                                    required property var currentValue
                                    required property var options
                                    Layout.fillWidth: true
                                    Text { text: label; color: Theme.textMuted; font.pixelSize: Theme.fontMeta; Layout.preferredWidth: 116 }
                                    Loader {
                                        Layout.fillWidth: true
                                        sourceComponent: kind === "bool" ? boolEditor : (kind === "enum" ? enumEditor : textEditor)
                                    }
                                    Component {
                                        id: boolEditor
                                        Switch {
                                            checked: Boolean(currentValue)
                                            onToggled: appController.applyOverlaySetting(fieldKey, checked)
                                        }
                                    }
                                    Component {
                                        id: enumEditor
                                        ComboBox {
                                            model: options || []
                                            textRole: "label"
                                            valueRole: "value"
                                            Component.onCompleted: currentIndex = Math.max(0, indexOfValue(String(currentValue)))
                                            onActivated: appController.applyOverlaySetting(fieldKey, currentValue)
                                        }
                                    }
                                    Component {
                                        id: textEditor
                                        TextField {
                                            text: String(currentValue)
                                            implicitHeight: Theme.controlHeight
                                            onEditingFinished: appController.applyOverlaySetting(fieldKey, text)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        LayoutTabs {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.dockHeight
            modelRef: layoutModel
            onLayoutChosen: appController.selectOverlayLayout(layoutId)
        }
    }
}
