import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  BlindSpotWidget — left/right blind spot indicators (160 x 80).
    Two colored rectangles that flash when a car is alongside.
    Simple, high-visibility awareness aid.                       */
Rectangle {
    id: root
    width: 160
    height: 80
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property bool leftCar: false
    property bool rightCar: false

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 8
            bottomMargin: 8
            leftMargin: 10
            rightMargin: 10
        }
        spacing: 6

        // ── Header ─────────────────────────────────────────────────
        Text {
            text: "BLIND SPOT"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 9
            font.weight: Font.Bold
            font.letterSpacing: 1.2
            color: Theme.Tokens.steel
            Layout.alignment: Qt.AlignHCenter
        }

        // ── Indicator row ──────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            // Left indicator
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 6
                color: root.leftCar
                       ? Qt.rgba(Theme.Tokens.safetyRed.r,
                                 Theme.Tokens.safetyRed.g,
                                 Theme.Tokens.safetyRed.b, 0.25)
                       : Qt.rgba(Theme.Tokens.steel.r,
                                 Theme.Tokens.steel.g,
                                 Theme.Tokens.steel.b, 0.06)
                border.width: 2
                border.color: root.leftCar
                              ? Qt.rgba(Theme.Tokens.safetyRed.r,
                                        Theme.Tokens.safetyRed.g,
                                        Theme.Tokens.safetyRed.b, 0.60)
                              : Qt.rgba(Theme.Tokens.steel.r,
                                        Theme.Tokens.steel.g,
                                        Theme.Tokens.steel.b, 0.12)

                Behavior on color { ColorAnimation { duration: 150 } }
                Behavior on border.color { ColorAnimation { duration: 150 } }

                Text {
                    anchors.centerIn: parent
                    text: root.leftCar ? "\u25C0 CAR" : "L"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: root.leftCar ? 11 : 14
                    font.weight: Font.Bold
                    color: root.leftCar
                           ? Theme.Tokens.safetyRed
                           : Theme.Tokens.steel
                    opacity: root.leftCar ? 1.0 : 0.3

                    Behavior on color { ColorAnimation { duration: 150 } }
                }

                // Flash animation when active
                SequentialAnimation on opacity {
                    running: root.leftCar
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.5; duration: 300 }
                    NumberAnimation { to: 1.0; duration: 300 }
                }
                opacity: root.leftCar ? 1.0 : 1.0
            }

            // Right indicator
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 6
                color: root.rightCar
                       ? Qt.rgba(Theme.Tokens.safetyRed.r,
                                 Theme.Tokens.safetyRed.g,
                                 Theme.Tokens.safetyRed.b, 0.25)
                       : Qt.rgba(Theme.Tokens.steel.r,
                                 Theme.Tokens.steel.g,
                                 Theme.Tokens.steel.b, 0.06)
                border.width: 2
                border.color: root.rightCar
                              ? Qt.rgba(Theme.Tokens.safetyRed.r,
                                        Theme.Tokens.safetyRed.g,
                                        Theme.Tokens.safetyRed.b, 0.60)
                              : Qt.rgba(Theme.Tokens.steel.r,
                                        Theme.Tokens.steel.g,
                                        Theme.Tokens.steel.b, 0.12)

                Behavior on color { ColorAnimation { duration: 150 } }
                Behavior on border.color { ColorAnimation { duration: 150 } }

                Text {
                    anchors.centerIn: parent
                    text: root.rightCar ? "CAR \u25B6" : "R"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: root.rightCar ? 11 : 14
                    font.weight: Font.Bold
                    color: root.rightCar
                           ? Theme.Tokens.safetyRed
                           : Theme.Tokens.steel
                    opacity: root.rightCar ? 1.0 : 0.3

                    Behavior on color { ColorAnimation { duration: 150 } }
                }

                // Flash animation when active
                SequentialAnimation on opacity {
                    running: root.rightCar
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.5; duration: 300 }
                    NumberAnimation { to: 1.0; duration: 300 }
                }
                opacity: root.rightCar ? 1.0 : 1.0
            }
        }
    }
}
