import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../Theme" as Theme
import "../Components" as Components

Item {
    id: root

    ScrollView {
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth

        // Background gradient
        Rectangle {
            width: parent.width
            height: Math.max(contentCol.implicitHeight + Theme.Tokens.xxl * 2, root.height)
            gradient: Gradient {
                GradientStop { position: 0.0; color: Theme.Tokens.void_ }
                GradientStop { position: 0.5; color: Theme.Tokens.surface }
                GradientStop { position: 1.0; color: "#030405" }
            }

            Column {
                id: contentCol
                anchors {
                    left: parent.left
                    right: parent.right
                    top: parent.top
                    margins: Theme.Tokens.xxl
                }
                spacing: Theme.Tokens.xl

                // === 1. Greeting ===
                Column {
                    width: parent.width
                    spacing: Theme.Tokens.xs

                    Text {
                        text: serviceVM.greeting
                        font.family: Theme.Typography.displayFamily
                        font.pixelSize: 32
                        font.weight: Font.Bold
                        font.letterSpacing: -0.3
                        color: Theme.Tokens.chalk
                    }

                    Text {
                        text: "Monitoring 4 simulators \u00b7 Last session 2h ago"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.bodySize
                        color: Theme.Tokens.steel
                    }
                }

                // === 2. Hero Card (recent session) ===
                Rectangle {
                    id: heroCard
                    visible: sessionVM.track !== ""
                    width: parent.width
                    implicitHeight: heroContent.implicitHeight + 56
                    radius: Theme.Tokens.radiusXl
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Theme.Tokens.surface }
                        GradientStop { position: 1.0; color: Qt.rgba(Theme.Tokens.pitOrange.r,
                                                                      Theme.Tokens.pitOrange.g,
                                                                      Theme.Tokens.pitOrange.b, 0.06) }
                    }
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                    Column {
                        id: heroContent
                        anchors {
                            left: parent.left
                            right: parent.right
                            top: parent.top
                            margins: 28
                            rightMargin: 32
                            leftMargin: 32
                        }
                        spacing: Theme.Tokens.lg

                        RowLayout {
                            width: parent.width
                            spacing: Theme.Tokens.xl

                            // Left: session info
                            Column {
                                Layout.fillWidth: true
                                spacing: Theme.Tokens.xs

                                Text {
                                    text: "LAST SESSION"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.microSize
                                    font.weight: Theme.Typography.microWeight
                                    font.letterSpacing: Theme.Typography.microSpacing
                                    color: Theme.Tokens.pitOrange
                                }

                                Text {
                                    text: sessionVM.track
                                    font.family: Theme.Typography.bodyFamily
                                    font.pixelSize: Theme.Typography.titleSize
                                    font.weight: Font.Bold
                                    color: Theme.Tokens.chalk
                                }

                                Text {
                                    text: sessionVM.car + " \u00b7 " + sessionVM.sim
                                    font.family: Theme.Typography.bodyFamily
                                    font.pixelSize: 13
                                    color: Theme.Tokens.steel
                                }
                            }

                            // Right: best lap
                            Column {
                                Layout.alignment: Qt.AlignRight | Qt.AlignTop
                                spacing: Theme.Tokens.xs

                                Text {
                                    text: "BEST LAP"
                                    anchors.right: parent.right
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.microSize
                                    font.weight: Theme.Typography.microWeight
                                    font.letterSpacing: Theme.Typography.microSpacing
                                    color: Theme.Tokens.pitOrange
                                }

                                Text {
                                    text: sessionVM.bestLapTime
                                    anchors.right: parent.right
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: 36
                                    font.weight: Font.Bold
                                    color: Theme.Tokens.chalk
                                }
                            }
                        }

                        // Sparkline (lap time trend)
                        Components.Sparkline {
                            width: parent.width
                            height: 48
                            lineColor: Theme.Tokens.pitOrange
                            values: sessionVM.speedHistory
                        }

                        // Action buttons
                        Row {
                            spacing: Theme.Tokens.sm

                            // Review Session
                            Rectangle {
                                width: reviewLabel.implicitWidth + Theme.Tokens.xl * 2
                                height: 36
                                radius: Theme.Tokens.radiusMd
                                color: reviewArea.containsMouse
                                       ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.18)
                                       : Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.10)
                                border.width: 1
                                border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.20)

                                Text {
                                    id: reviewLabel
                                    anchors.centerIn: parent
                                    text: "Review Session \u2192"
                                    font.family: Theme.Typography.bodyFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    font.weight: Font.DemiBold
                                    color: Theme.Tokens.pitOrange
                                }

                                MouseArea {
                                    id: reviewArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    // Will be wired when history/review flow is connected
                                }
                            }

                            // Open Folder
                            Rectangle {
                                width: folderLabel.implicitWidth + Theme.Tokens.xl * 2
                                height: 36
                                radius: Theme.Tokens.radiusMd
                                color: folderArea.containsMouse
                                       ? Theme.Tokens.subtle(Theme.Tokens.chalk)
                                       : "transparent"

                                Text {
                                    id: folderLabel
                                    anchors.centerIn: parent
                                    text: "Open Folder"
                                    font.family: Theme.Typography.bodyFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    font.weight: Font.DemiBold
                                    color: Theme.Tokens.steel
                                }

                                MouseArea {
                                    id: folderArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: serviceVM.openOutputFolder()
                                }
                            }
                        }
                    }
                }

                // === 3. Empty state (no session data) ===
                Rectangle {
                    visible: sessionVM.track === ""
                    width: parent.width
                    height: 200
                    radius: Theme.Tokens.radiusXl
                    color: Theme.Tokens.surface
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                    Column {
                        anchors.centerIn: parent
                        spacing: Theme.Tokens.md

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: "\uD83C\uDFC1"
                            font.pixelSize: 36
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: "Start any simulator to begin recording"
                            font.family: Theme.Typography.bodyFamily
                            font.pixelSize: Theme.Typography.headingSize
                            font.weight: Theme.Typography.headingWeight
                            color: Theme.Tokens.steel
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: "Lap Coach Logger is monitoring in the background"
                            font.family: Theme.Typography.bodyFamily
                            font.pixelSize: Theme.Typography.captionSize
                            color: Qt.rgba(Theme.Tokens.steel.r, Theme.Tokens.steel.g,
                                           Theme.Tokens.steel.b, 0.6)
                        }
                    }
                }

                // === 4. Metric Cards Grid (2x2) ===
                Grid {
                    width: parent.width
                    columns: parent.width > 700 ? 4 : 2
                    spacing: Theme.Tokens.md

                    Components.MetricCard {
                        width: (parent.width - parent.spacing * (parent.columns - 1)) / parent.columns
                        label: "Status"
                        value: serviceVM.status
                        subtitle: serviceVM.statusDetail
                    }

                    Components.MetricCard {
                        width: (parent.width - parent.spacing * (parent.columns - 1)) / parent.columns
                        label: "Sim"
                        value: serviceVM.sim || "\u2014"
                        subtitle: serviceVM.isMonitoring ? "Active" : "Idle"
                    }

                    Components.MetricCard {
                        width: (parent.width - parent.spacing * (parent.columns - 1)) / parent.columns
                        label: "Elapsed"
                        value: serviceVM.elapsedFormatted || "\u2014"
                        subtitle: "Session time"
                    }

                    Components.MetricCard {
                        width: (parent.width - parent.spacing * (parent.columns - 1)) / parent.columns
                        label: "Current Lap"
                        value: sessionVM.currentLap > 0 ? sessionVM.currentLap.toString() : "\u2014"
                        subtitle: sessionVM.track || "No session"
                    }
                }

                // === 5. Quick Actions Row ===
                Row {
                    spacing: Theme.Tokens.sm

                    Repeater {
                        model: [
                            { label: "Open Output Folder", action: "output" },
                            { label: "Toggle Overlay",     action: "overlay" },
                            { label: "Export Last Session", action: "export" }
                        ]

                        Rectangle {
                            required property var modelData
                            width: actionLabel.implicitWidth + Theme.Tokens.xl * 2
                            height: 34
                            radius: Theme.Tokens.radiusMd
                            color: actionArea.containsMouse
                                   ? Theme.Tokens.subtle(Theme.Tokens.chalk)
                                   : "transparent"
                            border.width: 1
                            border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                            Text {
                                id: actionLabel
                                anchors.centerIn: parent
                                text: modelData.label
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.captionSize
                                font.weight: Font.DemiBold
                                color: Theme.Tokens.steel
                            }

                            MouseArea {
                                id: actionArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (modelData.action === "output")
                                        serviceVM.openOutputFolder()
                                    // overlay and export will be wired in later tasks
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
