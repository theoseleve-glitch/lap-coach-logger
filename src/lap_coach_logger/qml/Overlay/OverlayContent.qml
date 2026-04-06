import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme
import "../Components" as Components

Item {
    id: root

    Rectangle {
        anchors.fill: parent
        radius: Theme.Tokens.radiusXl
        color: Qt.rgba(Theme.Tokens.void_.r,
                       Theme.Tokens.void_.g,
                       Theme.Tokens.void_.b, 0.88)
        border.width: 1
        border.color: Theme.Tokens.medium(Theme.Tokens.chalk)

        ColumnLayout {
            anchors {
                fill: parent
                topMargin: 16
                bottomMargin: 16
                leftMargin: 20
                rightMargin: 20
            }
            spacing: Theme.Tokens.md

            // ── 1. Context line ──────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: {
                        var parts = []
                        if (overlayVM && overlayVM.trackName)
                            parts.push(overlayVM.trackName)
                        if (overlayVM && overlayVM.carClass)
                            parts.push(overlayVM.carClass)
                        if (overlayVM && overlayVM.currentLap > 0)
                            parts.push("Lap " + overlayVM.currentLap)
                        return parts.join(" \u00B7 ")
                    }
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    color: Qt.rgba(Theme.Tokens.chalk.r,
                                   Theme.Tokens.chalk.g,
                                   Theme.Tokens.chalk.b, 0.70)
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                // Recording indicator
                RowLayout {
                    spacing: 4
                    visible: overlayVM ? overlayVM.isRecording : false

                    Rectangle {
                        width: 5
                        height: 5
                        radius: 2.5
                        color: Theme.Tokens.acidGreen

                        SequentialAnimation on opacity {
                            loops: Animation.Infinite
                            NumberAnimation {
                                from: 1.0; to: 0.3
                                duration: Theme.Motion.recordingPulseDuration / 2
                            }
                            NumberAnimation {
                                from: 0.3; to: 1.0
                                duration: Theme.Motion.recordingPulseDuration / 2
                            }
                        }
                    }

                    Text {
                        text: "REC"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Font.DemiBold
                        color: Theme.Tokens.acidGreen
                    }

                    Text {
                        text: overlayVM ? overlayVM.elapsedFormatted : "0:00"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Font.DemiBold
                        color: Theme.Tokens.acidGreen
                    }
                }
            }

            // ── 2. Three times ───────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                // CURRENT
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: "CURRENT"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Theme.Typography.microWeight
                        font.letterSpacing: Theme.Typography.microSpacing
                        color: "#646464"
                    }

                    Text {
                        text: overlayVM && overlayVM.currentTime
                              ? overlayVM.currentTime : "X:XX.\u2014"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 22
                        font.weight: Font.Bold
                        color: Theme.Tokens.chalk
                    }
                }

                // LAST
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: "LAST"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Theme.Typography.microWeight
                        font.letterSpacing: Theme.Typography.microSpacing
                        color: "#646464"
                    }

                    Text {
                        text: overlayVM && overlayVM.lastTime
                              ? overlayVM.lastTime : "\u2014:\u2014\u2014.\u2014"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 22
                        font.weight: Font.Bold
                        color: Theme.Tokens.chalk
                    }

                    // Delta
                    Text {
                        visible: overlayVM ? overlayVM.lastDelta !== 0 : false
                        text: {
                            if (!overlayVM || overlayVM.lastDelta === 0) return ""
                            var sign = overlayVM.lastDelta > 0 ? "+" : ""
                            return sign + overlayVM.lastDelta.toFixed(3)
                        }
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.microSize
                        color: {
                            if (!overlayVM) return Theme.Tokens.steel
                            return overlayVM.lastDelta > 0
                                   ? Theme.Tokens.safetyRed
                                   : Theme.Tokens.acidGreen
                        }
                    }
                }

                // BEST
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: "BEST"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Theme.Typography.microWeight
                        font.letterSpacing: Theme.Typography.microSpacing
                        color: Theme.Tokens.pitOrange
                    }

                    Text {
                        text: overlayVM && overlayVM.bestTime
                              ? overlayVM.bestTime : "\u2014:\u2014\u2014.\u2014"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 22
                        font.weight: Font.Bold
                        color: Theme.Tokens.pitOrange
                    }
                }
            }

            // ── 3. Sector bars ───────────────────────────
            Components.SectorBars {
                Layout.fillWidth: true
                states: overlayVM ? overlayVM.sectorStates : ["pending", "pending", "pending"]
            }

            // ── 4. Speed + inputs ────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.Tokens.md

                // Speed
                RowLayout {
                    spacing: 4

                    Text {
                        text: overlayVM ? String(Math.round(overlayVM.speed)) : "0"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 16
                        font.weight: Font.Bold
                        color: Qt.rgba(Theme.Tokens.chalk.r,
                                       Theme.Tokens.chalk.g,
                                       Theme.Tokens.chalk.b, 0.80)
                    }

                    Text {
                        text: "km/h"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.microSize
                        color: "#646464"
                        Layout.alignment: Qt.AlignBottom
                    }
                }

                // Divider
                Rectangle {
                    width: 1
                    height: 14
                    color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.15)
                    Layout.alignment: Qt.AlignVCenter
                }

                // Throttle / Brake bars
                Components.ThrottleBrakeBar {
                    throttle: overlayVM ? overlayVM.throttlePct : 0.0
                    brake: overlayVM ? overlayVM.brakePct : 0.0
                    Layout.fillWidth: true
                }
            }
        }
    }
}
