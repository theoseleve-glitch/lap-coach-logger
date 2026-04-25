import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../Theme" as Theme
import "../Components" as Components

Item {
    id: root

    signal reviewRequested(string folder)

    Column {
        anchors {
            fill: parent
            margins: Theme.Tokens.xl
        }
        spacing: Theme.Tokens.lg

        // === Header row ===
        RowLayout {
            width: parent.width
            spacing: Theme.Tokens.lg

            // Left: title + count
            Column {
                Layout.fillWidth: true
                spacing: Theme.Tokens.xs

                Text {
                    text: "History"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: 24
                    font.weight: Font.Bold
                    color: Theme.Tokens.chalk
                }

                Text {
                    text: historyVM.count + " sessions"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.captionSize
                    color: Theme.Tokens.steel
                }
            }

            // Right: search + filter
            Components.SearchBar {
                Layout.preferredWidth: 240
                placeholder: "Search tracks, sims..."
                onSearchTextChanged: function(searchText) {
                    historyVM.setSearchText(searchText)
                }
            }

            // Sim filter ComboBox
            Rectangle {
                Layout.preferredWidth: 120
                height: 36
                radius: Theme.Tokens.radiusMd
                color: Theme.Tokens.raised
                border.width: 1
                border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                RowLayout {
                    anchors {
                        fill: parent
                        leftMargin: Theme.Tokens.md
                        rightMargin: Theme.Tokens.md
                    }
                    spacing: Theme.Tokens.xs

                    Text {
                        text: historyVM.simFilter || "All Sims"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.captionSize
                        color: historyVM.simFilter ? Theme.Tokens.chalk : Theme.Tokens.steel
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    Text {
                        text: "\u25BE"
                        font.pixelSize: 10
                        color: Theme.Tokens.steel
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: simFilterMenu.open()
                }

                Menu {
                    id: simFilterMenu
                    y: parent.height + 4

                    MenuItem {
                        text: "All Sims"
                        onTriggered: historyVM.setSimFilter("")
                    }
                    MenuItem {
                        text: "iRacing"
                        onTriggered: historyVM.setSimFilter("iRacing")
                    }
                    MenuItem {
                        text: "ACC"
                        onTriggered: historyVM.setSimFilter("ACC")
                    }
                    MenuItem {
                        text: "Le Mans Ultimate"
                        onTriggered: historyVM.setSimFilter("Le Mans Ultimate")
                    }
                }
            }
        }

        // === Empty state ===
        Rectangle {
            visible: historyVM.count === 0
            width: parent.width
            height: 200
            radius: Theme.Tokens.radiusLg
            color: Theme.Tokens.surface
            border.width: 1
            border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

            Column {
                anchors.centerIn: parent
                spacing: Theme.Tokens.md

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "No sessions yet"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.headingSize
                    font.weight: Theme.Typography.headingWeight
                    color: Theme.Tokens.steel
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Complete a session in any simulator to see it here"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.captionSize
                    color: Qt.rgba(Theme.Tokens.steel.r, Theme.Tokens.steel.g,
                                   Theme.Tokens.steel.b, 0.6)
                }
            }
        }

        // === Session list ===
        ListView {
            id: sessionList
            visible: historyVM.count > 0
            width: parent.width
            Layout.fillHeight: true
            height: parent.height - y
            clip: true
            spacing: Theme.Tokens.sm
            model: historyVM.sessions

            // Date group headers
            section.property: "date"
            section.delegate: Item {
                required property string section
                width: sessionList.width
                height: 36

                Text {
                    anchors {
                        left: parent.left
                        bottom: parent.bottom
                        bottomMargin: Theme.Tokens.xs
                    }
                    text: section
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Theme.Typography.microSize
                    font.weight: Theme.Typography.microWeight
                    font.letterSpacing: Theme.Typography.microSpacing
                    color: Theme.Tokens.steel
                }
            }

            delegate: Components.SessionCard {
                required property var modelData
                required property int index

                width: sessionList.width
                simName: modelData.sim || ""
                track: modelData.track || ""
                metadata: (modelData.car || "") + " \u00b7 "
                          + (modelData.laps || 0) + " laps \u00b7 "
                          + (modelData.time || "")
                bestLap: modelData.best_lap_formatted || ""
                grade: modelData.quality_grade || ""
                gradeColor: {
                    var g = modelData.quality_grade || ""
                    if (g === "A+" || g === "A") return Theme.Tokens.acidGreen
                    if (g === "B+") return Theme.Tokens.marshalYellow
                    return Theme.Tokens.steel
                }

                onClicked: {
                    var folder = historyVM.folderAt(index)
                    if (folder) root.reviewRequested(folder)
                }

                onContextMenuRequested: function(x, y) {
                    contextMenu.sessionIndex = index
                    contextMenu.popup()
                }
            }

            // Scroll performance
            cacheBuffer: 400
            reuseItems: true
        }
    }

    // Context menu for session cards
    Menu {
        id: contextMenu
        property int sessionIndex: -1

        MenuItem {
            // T070: per Q95, export/deep-analysis lives in lap-webapp;
            // this menu item now opens the webapp instead of doing a
            // local CSV export.
            text: "View in webapp"
            onTriggered: serviceVM.viewSessionsInWebapp()
        }
        MenuItem {
            text: "Copy Session ID"
            onTriggered: {
                if (contextMenu.sessionIndex >= 0) {
                    var sid = historyVM.sessionIdAt(contextMenu.sessionIndex)
                    // Clipboard copy handled by backend
                }
            }
        }
        MenuSeparator {}
        MenuItem {
            text: "Mark Ignored"
        }
        MenuItem {
            text: "Delete"
        }
    }
}
