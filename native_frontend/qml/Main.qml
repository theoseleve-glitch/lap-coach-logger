import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LapCoachDesktop

ApplicationWindow {
    id: window
    visible: true
    width: 1600
    height: 960
    minimumWidth: 1280
    minimumHeight: 820
    color: Theme.windowBg
    title: "LAP COACH Native"

    header: SurfacePane {
        height: Theme.toolbarHeight
        color: Theme.chromeBg
        radius: 0
        border.color: Theme.border

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.space5
            anchors.rightMargin: Theme.space5
            spacing: Theme.space5

            Text {
                text: "LAP COACH"
                color: Theme.text
                font.pixelSize: 16
                font.weight: Font.DemiBold
            }

            Text {
                text: appController.statusLabel
                color: Theme.text
                font.pixelSize: Theme.fontBody
            }

            Text {
                text: appController.statusDetail
                color: Theme.textMuted
                font.pixelSize: Theme.fontMeta
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            ToolbarButton {
                text: "Resume"
                emphasis: !appController.monitoringActive
                onClicked: appController.startMonitoring()
            }

            ToolbarButton {
                text: "Pause"
                danger: true
                onClicked: appController.stopMonitoring()
            }

            StatusBadge {
                label: appController.connectionLabel
                tone: "neutral"
            }
        }
    }

    footer: SurfacePane {
        height: Theme.statusHeight
        color: Theme.chromeBg
        radius: 0
        border.color: Theme.border

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.space5
            anchors.rightMargin: Theme.space5
            spacing: Theme.space5

            Text {
                text: "Native Qt 6/QML shell"
                color: Theme.textMuted
                font.pixelSize: Theme.fontMeta
            }
            Item { Layout.fillWidth: true }
            Text {
                text: appController.currentScreen.toUpperCase()
                color: Theme.text
                font.pixelSize: Theme.fontMeta
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: Theme.space4

        SurfacePane {
            Layout.fillHeight: true
            Layout.preferredWidth: Theme.navWidth
            color: Theme.chromeBg

            ListView {
                anchors.fill: parent
                anchors.margins: Theme.space4
                model: appController.navigationModel
                spacing: Theme.space3

                delegate: Rectangle {
                    required property string screenId
                    required property string label
                    width: ListView.view.width
                    height: 44
                    radius: Theme.radiusSm
                    color: appController.currentScreen === screenId ? Theme.selection : "transparent"
                    border.width: 1
                    border.color: appController.currentScreen === screenId ? Theme.selectionBorder : Theme.border

                    Text {
                        anchors.centerIn: parent
                        text: label
                        color: Theme.text
                        font.pixelSize: Theme.fontBody
                        font.weight: Font.DemiBold
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: appController.navigate(screenId)
                    }
                }
            }
        }

        Loader {
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: {
                switch (appController.currentScreen) {
                case "dashboard": return dashboardScreen
                case "live": return liveScreen
                case "logs": return logsScreen
                case "history": return historyScreen
                case "review": return reviewScreen
                default: return overlayScreen
                }
            }
        }
    }

    Component { id: dashboardScreen; DashboardScreen { state: appController.dashboardState } }
    Component { id: liveScreen; LiveScreen { state: appController.liveState } }
    Component { id: logsScreen; LogsScreen { modelRef: appController.logModel } }
    Component { id: historyScreen; HistoryScreen { modelRef: appController.historyModel } }
    Component {
        id: overlayScreen
        OverlayScreen {
            state: appController.overlayState
            categoryModel: appController.overlayCategoryModel
            overlayModel: appController.overlayLibraryModel
            layoutModel: appController.overlayLayoutModel
        }
    }
    Component { id: reviewScreen; ReviewScreen { state: appController.reviewState } }
}
