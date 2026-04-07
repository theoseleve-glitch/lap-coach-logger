import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  GarageCoverWidget -- BRB / intermission screen for streams (320x180).
    "IN THE GARAGE" with subtitle and optional branding.
    Category: streaming -- uses racingPurple accent.                       */
Rectangle {
    id: root
    width: 320
    height: 180
    color: "transparent"

    // -- public API ----------------------------------------------------------
    property string message: "IN THE GARAGE"
    property string subMessage: ""
    property bool   showLogo: true

    // -- internal ------------------------------------------------------------
    readonly property string _safeMessage:    (message || "").length > 0
                                              ? message : "IN THE GARAGE"
    readonly property string _safeSubMessage: subMessage || ""

    // -- content -------------------------------------------------------------
    Rectangle {
        anchors.fill: parent
        radius: Theme.Tokens.radiusMd
        color: Qt.rgba(0, 0, 0, 0.75)
        border.width: 1
        border.color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.20)

        // Subtle breathing opacity on the whole card
        SequentialAnimation on opacity {
            loops: Animation.Infinite
            NumberAnimation { from: 1.0; to: 0.88; duration: 3000;
                              easing.type: Easing.InOutSine }
            NumberAnimation { from: 0.88; to: 1.0; duration: 3000;
                              easing.type: Easing.InOutSine }
        }

        ColumnLayout {
            anchors.centerIn: parent
            spacing: Theme.Tokens.md - 2

            // -- Logo placeholder --------------------------------------------
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                visible: root.showLogo
                width: 40; height: 40; radius: Theme.Tokens.radiusXl
                color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.12)
                border.width: 1
                border.color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.25)

                Text {
                    anchors.centerIn: parent
                    text: "LC"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Theme.Typography.bodySize
                    font.weight: Font.Bold
                    color: Theme.Tokens.racingPurple
                }
            }

            // -- Main message ------------------------------------------------
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: root._safeMessage
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.titleSize
                font.weight: Font.Bold
                font.letterSpacing: 2.0
                color: Theme.Tokens.chalk
            }

            // -- Sub-message -------------------------------------------------
            Text {
                Layout.alignment: Qt.AlignHCenter
                visible: root._safeSubMessage.length > 0
                text: root._safeSubMessage
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 11
                color: Theme.Tokens.steel
                opacity: 0.7
            }

            // -- Racing purple accent line -----------------------------------
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: 60; height: 2; radius: 1
                color: Theme.Tokens.racingPurple
                opacity: 0.5
            }

            // -- Streaming dot indicator -------------------------------------
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: Theme.Tokens.xs + 2

                Rectangle {
                    width: 5; height: 5; radius: 2.5
                    color: Theme.Tokens.racingPurple

                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.3; duration: 1000 }
                        NumberAnimation { from: 0.3; to: 1.0; duration: 1000 }
                    }
                }

                Text {
                    text: "BE RIGHT BACK"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.Bold
                    font.letterSpacing: 1.0
                    color: Theme.Tokens.racingPurple
                    opacity: 0.6
                }
            }
        }
    }
}
