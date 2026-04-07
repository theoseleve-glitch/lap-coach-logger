import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../Theme" as Theme
import "../Components" as Components

Item {
    id: root

    readonly property bool isRecording: serviceVM.status === "Recording"

    // === Idle state ===
    Column {
        anchors.centerIn: parent
        spacing: Theme.Tokens.md
        visible: !root.isRecording

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Waiting for simulator"
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: Theme.Typography.headingSize
            font.weight: Theme.Typography.headingWeight
            color: Theme.Tokens.steel
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: serviceVM.statusDetail
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: Theme.Typography.bodySize
            color: Qt.rgba(Theme.Tokens.steel.r, Theme.Tokens.steel.g,
                           Theme.Tokens.steel.b, 0.6)
        }
    }

    // === Active state ===
    ScrollView {
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth
        visible: root.isRecording

        Column {
            id: liveContent
            anchors {
                left: parent.left
                right: parent.right
                top: parent.top
                margins: Theme.Tokens.xl
            }
            spacing: Theme.Tokens.xl

            // --- Session header ---
            RowLayout {
                width: parent.width
                spacing: Theme.Tokens.xl

                // Left: session info
                Column {
                    Layout.fillWidth: true
                    spacing: Theme.Tokens.xs

                    Row {
                        spacing: Theme.Tokens.sm

                        // Recording indicator dot
                        Rectangle {
                            width: 8
                            height: 8
                            radius: 4
                            color: Theme.Tokens.acidGreen
                            anchors.verticalCenter: parent.verticalCenter

                            SequentialAnimation on opacity {
                                loops: Animation.Infinite
                                NumberAnimation { to: 0.3; duration: Theme.Motion.recordingPulseDuration / 2 }
                                NumberAnimation { to: 1.0; duration: Theme.Motion.recordingPulseDuration / 2 }
                            }
                        }

                        Text {
                            text: "LIVE SESSION"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.acidGreen
                        }
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
                        font.pixelSize: Theme.Typography.captionSize
                        color: Theme.Tokens.steel
                    }
                }

                // Right: current lap
                Column {
                    Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                    spacing: Theme.Tokens.xs

                    Text {
                        text: "CURRENT LAP"
                        anchors.right: parent.right
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Theme.Typography.microWeight
                        font.letterSpacing: Theme.Typography.microSpacing
                        color: Theme.Tokens.steel
                    }

                    Text {
                        text: sessionVM.currentLap.toString()
                        anchors.right: parent.right
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 48
                        font.weight: Font.Bold
                        color: Theme.Tokens.chalk
                    }
                }
            }

            // --- Three MetricCards ---
            RowLayout {
                width: parent.width
                spacing: Theme.Tokens.md

                Components.MetricCard {
                    Layout.fillWidth: true
                    label: "Last Lap"
                    value: sessionVM.lastLapTime || "\u2014"
                    subtitle: sessionVM.lastLapDelta || ""
                }

                Components.MetricCard {
                    Layout.fillWidth: true
                    label: "Best Lap"
                    value: sessionVM.bestLapTime || "\u2014"
                    subtitle: sessionVM.bestLapNumber > 0
                             ? ("Lap " + sessionVM.bestLapNumber) : ""
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.30)
                }

                Components.MetricCard {
                    Layout.fillWidth: true
                    label: "Consistency"
                    value: sessionVM.consistencyPct > 0
                           ? (sessionVM.consistencyPct.toFixed(1) + "%") : "\u2014"
                    subtitle: sessionVM.consistencySigma || ""
                }
            }

            // --- Trace panels side by side ---
            RowLayout {
                width: parent.width
                spacing: Theme.Tokens.md

                // Speed sparkline panel
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 120
                    radius: Theme.Tokens.radiusLg
                    color: Theme.Tokens.surface
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                    Column {
                        anchors {
                            fill: parent
                            margins: Theme.Tokens.lg
                        }
                        spacing: Theme.Tokens.sm

                        RowLayout {
                            width: parent.width

                            Text {
                                text: "SPEED"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Theme.Typography.microWeight
                                font.letterSpacing: Theme.Typography.microSpacing
                                color: Theme.Tokens.steel
                            }

                            Item { Layout.fillWidth: true }

                            Text {
                                text: sessionVM.speedKph > 0
                                      ? (Math.round(sessionVM.speedKph) + " km/h") : "\u2014"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.bodySize
                                font.weight: Font.Bold
                                color: Theme.Tokens.pitOrange
                            }
                        }

                        Components.Sparkline {
                            width: parent.width
                            height: 60
                            lineColor: Theme.Tokens.pitOrange
                            values: sessionVM.speedHistory
                            minValue: 0
                            maxValue: 350
                        }
                    }
                }

                // Throttle/Brake panel
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 120
                    radius: Theme.Tokens.radiusLg
                    color: Theme.Tokens.surface
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                    Column {
                        anchors {
                            fill: parent
                            margins: Theme.Tokens.lg
                        }
                        spacing: Theme.Tokens.md

                        Text {
                            text: "INPUTS"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.steel
                        }

                        // Throttle row
                        RowLayout {
                            width: parent.width
                            spacing: Theme.Tokens.sm

                            Text {
                                text: "THR"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Font.Bold
                                color: Theme.Tokens.acidGreen
                            }

                            Components.ThrottleBrakeBar {
                                Layout.fillWidth: true
                                throttle: sessionVM.throttlePct / 100.0
                                brake: 0
                            }

                            Text {
                                text: Math.round(sessionVM.throttlePct) + "%"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.captionSize
                                font.weight: Font.Bold
                                color: Theme.Tokens.acidGreen
                                Layout.minimumWidth: 36
                                horizontalAlignment: Text.AlignRight
                            }
                        }

                        // Brake row
                        RowLayout {
                            width: parent.width
                            spacing: Theme.Tokens.sm

                            Text {
                                text: "BRK"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Font.Bold
                                color: Theme.Tokens.safetyRed
                            }

                            Components.ThrottleBrakeBar {
                                Layout.fillWidth: true
                                throttle: 0
                                brake: sessionVM.brakePct / 100.0
                            }

                            Text {
                                text: Math.round(sessionVM.brakePct) + "%"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.captionSize
                                font.weight: Font.Bold
                                color: Theme.Tokens.safetyRed
                                Layout.minimumWidth: 36
                                horizontalAlignment: Text.AlignRight
                            }
                        }
                    }
                }
            }

            // --- Lap table ---
            Rectangle {
                width: parent.width
                implicitHeight: lapTableCol.implicitHeight + Theme.Tokens.xl * 2
                radius: Theme.Tokens.radiusLg
                color: Theme.Tokens.surface
                border.width: 1
                border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                Column {
                    id: lapTableCol
                    anchors {
                        left: parent.left
                        right: parent.right
                        top: parent.top
                        margins: Theme.Tokens.xl
                    }
                    spacing: 0

                    // Table header
                    RowLayout {
                        width: parent.width
                        height: 32
                        spacing: Theme.Tokens.sm

                        Text {
                            text: "LAP"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.steel
                            Layout.preferredWidth: 50
                        }

                        Text {
                            text: "TIME"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.steel
                            Layout.fillWidth: true
                        }

                        Text {
                            text: "DELTA"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.steel
                            Layout.preferredWidth: 100
                            horizontalAlignment: Text.AlignRight
                        }

                        Text {
                            text: "STATUS"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.steel
                            Layout.preferredWidth: 80
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    // Separator
                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Theme.Tokens.subtle(Theme.Tokens.chalk)
                    }

                    // Lap rows
                    Repeater {
                        model: sessionVM.laps

                        Rectangle {
                            required property var modelData
                            required property int index

                            readonly property bool isBest: modelData.is_best === true

                            width: parent.width
                            height: 36
                            color: isBest ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.08)
                                          : "transparent"
                            radius: isBest ? Theme.Tokens.radiusSm : 0

                            RowLayout {
                                anchors {
                                    fill: parent
                                    leftMargin: Theme.Tokens.xs
                                    rightMargin: Theme.Tokens.xs
                                }
                                spacing: Theme.Tokens.sm

                                Text {
                                    text: modelData.lap !== undefined ? modelData.lap.toString() : (index + 1).toString()
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    font.weight: isBest ? Font.Bold : Font.Normal
                                    color: isBest ? Theme.Tokens.pitOrange : Theme.Tokens.chalk
                                    Layout.preferredWidth: 50
                                }

                                Text {
                                    text: modelData.time || "\u2014"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    font.weight: Font.DemiBold
                                    color: isBest ? Theme.Tokens.pitOrange : Theme.Tokens.chalk
                                    Layout.fillWidth: true
                                }

                                Text {
                                    text: modelData.delta || ""
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    color: {
                                        if (!modelData.delta) return Theme.Tokens.steel
                                        if (modelData.delta.indexOf("-") === 0) return Theme.Tokens.acidGreen
                                        return Theme.Tokens.safetyRed
                                    }
                                    Layout.preferredWidth: 100
                                    horizontalAlignment: Text.AlignRight
                                }

                                Text {
                                    text: modelData.status || ""
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.microSize
                                    font.weight: Font.Bold
                                    color: {
                                        if (modelData.status === "clean") return Theme.Tokens.acidGreen
                                        if (modelData.status === "track_limits") return Theme.Tokens.marshalYellow
                                        return Theme.Tokens.steel
                                    }
                                    Layout.preferredWidth: 80
                                    horizontalAlignment: Text.AlignRight
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
