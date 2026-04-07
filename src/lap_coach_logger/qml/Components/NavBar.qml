import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme

Rectangle {
    id: root

    property string currentPage: "dashboard"
    property string status: "Idle"
    property string statusDetail: ""
    property bool isMonitoring: false
    property string elapsedFormatted: ""

    signal pageRequested(string pageId)
    signal settingsRequested()
    signal pauseRequested()
    signal resumeRequested()

    height: 52
    color: Theme.Tokens.subtle(Theme.Tokens.surface, 0.85)

    // Bottom border — green tint when recording
    Rectangle {
        anchors {
            left: parent.left
            right: parent.right
            bottom: parent.bottom
        }
        height: 1
        color: root.status === "Recording"
               ? Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.12)
               : Theme.Tokens.subtle(Theme.Tokens.chalk)
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.Tokens.xl
        anchors.rightMargin: Theme.Tokens.xl
        spacing: Theme.Tokens.md

        // === 1. Brand mark ===
        Row {
            spacing: 10

            // Monogram square
            Rectangle {
                width: 28
                height: 28
                radius: Theme.Tokens.radiusSm
                color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.15)

                Text {
                    anchors.centerIn: parent
                    text: "L"
                    font.family: Theme.Typography.displayFamily
                    font.pixelSize: 16
                    font.weight: Font.Bold
                    color: Theme.Tokens.pitOrange
                }
            }

            // Brand name
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "LAP COACH"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: 14
                font.weight: Font.Bold
                font.letterSpacing: 1
                color: Theme.Tokens.chalk
            }
        }

        // Separator space before tabs
        Item { width: Theme.Tokens.sm }

        // === 2. Nav tabs ===
        Row {
            spacing: 4

            Repeater {
                model: [
                    { pageId: "dashboard", label: "Dashboard" },
                    { pageId: "live",      label: "Live" },
                    { pageId: "history",   label: "History" }
                ]

                delegate: Rectangle {
                    id: tabBtn
                    required property var modelData
                    readonly property bool isActive: root.currentPage === modelData.pageId

                    width: tabLabel.implicitWidth + Theme.Tokens.lg * 2
                    height: 30
                    radius: Theme.Tokens.radiusMd
                    color: isActive ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.12)
                                    : "transparent"
                    border.width: isActive ? 1 : 0
                    border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.20)

                    scale: tabArea.pressed ? Theme.Motion.pressScale
                         : tabArea.containsMouse ? Theme.Motion.hoverScale
                         : 1.0

                    Behavior on scale {
                        NumberAnimation {
                            duration: tabArea.pressed ? Theme.Motion.pressDuration
                                                     : Theme.Motion.hoverDuration
                            easing.type: Easing.OutBack
                        }
                    }

                    Text {
                        id: tabLabel
                        anchors.centerIn: parent
                        text: tabBtn.modelData.label
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: 12
                        font.weight: tabBtn.isActive ? Font.DemiBold : Font.Normal
                        color: tabBtn.isActive ? Theme.Tokens.chalk : Theme.Tokens.steel
                    }

                    MouseArea {
                        id: tabArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.pageRequested(tabBtn.modelData.pageId)
                    }
                }
            }
        }

        // === 3. Spacer ===
        Item { Layout.fillWidth: true }

        // === 4. StatusPill ===
        StatusPill {
            status: root.status
            elapsed: root.elapsedFormatted
        }

        // === 5. PAUSE button (only when Recording) ===
        Rectangle {
            visible: root.status === "Recording"
            width: pauseLabel.implicitWidth + Theme.Tokens.lg * 2
            height: 26
            radius: Theme.Tokens.radiusSm
            color: Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.10)
            border.width: 1
            border.color: Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.20)

            Text {
                id: pauseLabel
                anchors.centerIn: parent
                text: "PAUSE"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: 10
                font.weight: Font.Bold
                color: "#FF7A7A"
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.pauseRequested()
            }
        }

        // === 6. Gear icon button ===
        Rectangle {
            id: gearBtn
            width: 36
            height: 36
            radius: Theme.Tokens.radiusMd
            color: gearArea.containsMouse
                   ? Theme.Tokens.subtle(Theme.Tokens.chalk)
                   : "transparent"

            Text {
                anchors.centerIn: parent
                text: "\u2699"
                font.pixelSize: 16
                color: Theme.Tokens.steel
            }

            MouseArea {
                id: gearArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.settingsRequested()
            }
        }
    }
}
