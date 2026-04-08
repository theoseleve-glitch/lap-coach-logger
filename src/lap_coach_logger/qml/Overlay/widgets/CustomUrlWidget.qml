import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  CustomUrlWidget -- browser widget placeholder for streams (300x200).
    Shows a URL label and "CUSTOM CONTENT" placeholder area.
    Category: streaming -- uses racingPurple accent.                      */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 300
    height: 200
    color: "transparent"

    // -- public API ----------------------------------------------------------
    property string url: "https://example.com"
    property string label: "Custom Content"

    // -- internal ------------------------------------------------------------
    readonly property string _safeUrl:   (url || "").length > 0   ? url   : "---"
    readonly property string _safeLabel: (label || "").length > 0 ? label : "---"

    // -- content -------------------------------------------------------------
    Rectangle {
        anchors.fill: parent
        radius: Theme.Tokens.radiusSm
        color: Qt.rgba(0, 0, 0, 0.55)
        border.width: 1
        border.color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.15)

        ColumnLayout {
            anchors {
                fill: parent
                topMargin: Theme.Tokens.sm
                bottomMargin: Theme.Tokens.sm
                leftMargin: Theme.Tokens.md - 2
                rightMargin: Theme.Tokens.md - 2
            }
            spacing: 0

            // -- Header ------------------------------------------------------
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.Tokens.xs + 2

                Text {
                    text: "URL"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(9 * root.fontScale)
                    font.weight: Font.Bold
                    font.letterSpacing: 1.2
                    color: Theme.Tokens.steel
                }

                // Streaming badge
                Rectangle {
                    implicitWidth: urlBadge.implicitWidth + Theme.Tokens.sm
                    implicitHeight: 14
                    radius: 3
                    color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.15)
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.30)

                    Text {
                        id: urlBadge
                        anchors.centerIn: parent
                        text: "STREAM"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Math.round(7 * root.fontScale)
                        font.weight: Font.Bold
                        color: Theme.Tokens.racingPurple
                    }
                }

                Item { Layout.fillWidth: true }
            }

            // -- URL display -------------------------------------------------
            Text {
                Layout.fillWidth: true
                text: root._safeUrl
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(8 * root.fontScale)
                color: Theme.Tokens.racingPurple
                elide: Text.ElideMiddle
                opacity: 0.7
            }

            // -- Separator ---------------------------------------------------
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: Theme.Tokens.xs + 2
                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width; height: 1
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 0.5;
                                       color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.12) }
                        GradientStop { position: 1.0; color: "transparent" }
                    }
                }
            }

            // -- Placeholder content area ------------------------------------
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: Theme.Tokens.radiusSm
                color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.04)
                border.width: 1
                border.color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.08)

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: Theme.Tokens.xs + 2

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "CUSTOM CONTENT"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Font.Bold
                        font.letterSpacing: 1.0
                        color: Theme.Tokens.racingPurple
                        opacity: 0.6
                    }

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: root._safeLabel
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.captionSize
                        font.weight: Font.Bold
                        color: Theme.Tokens.chalk
                    }

                    // Globe icon placeholder
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        width: 24; height: 24; radius: 12
                        color: Theme.Tokens.medium(Theme.Tokens.racingPurple)
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.20)

                        Text {
                            anchors.centerIn: parent
                            text: "\u25CB"
                            font.pixelSize: Theme.Typography.bodySize
                            color: Theme.Tokens.racingPurple
                            opacity: 0.5
                        }
                    }
                }
            }
        }
    }
}
