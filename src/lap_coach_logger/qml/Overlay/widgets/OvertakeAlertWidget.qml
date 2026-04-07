import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  OvertakeAlertWidget — overtake/defend alert banner (240 x 60).
    Shows "OVERTAKE" or "DEFEND" with direction arrow and
    optional car number. Animated text with slide-in.            */
Rectangle {
    id: root
    width: 240
    height: 60
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    // "none" | "overtake_left" | "overtake_right" |
    //          "defend_left"   | "defend_right"
    property string alertType: "none"
    property string carNumber: ""

    readonly property bool isActive: alertType !== "none"
    readonly property bool isOvertake: alertType.indexOf("overtake") === 0
    readonly property bool isLeft: alertType.indexOf("_left") !== -1

    readonly property string alertLabel: {
        if (isOvertake) return "OVERTAKE"
        if (alertType.indexOf("defend") === 0) return "DEFEND"
        return ""
    }

    readonly property string directionArrow: {
        if (!isActive) return ""
        return isLeft ? "\u25C0" : "\u25B6"
    }

    readonly property color alertColor: {
        if (isOvertake) return Theme.Tokens.acidGreen
        if (alertType.indexOf("defend") === 0) return Theme.Tokens.safetyRed
        return Theme.Tokens.steel
    }

    // ── Alert panel ────────────────────────────────────────────────
    Rectangle {
        anchors {
            fill: parent
            margins: 4
        }
        radius: 6
        color: root.isActive
               ? Qt.rgba(root.alertColor.r,
                          root.alertColor.g,
                          root.alertColor.b, 0.15)
               : Qt.rgba(Theme.Tokens.steel.r,
                          Theme.Tokens.steel.g,
                          Theme.Tokens.steel.b, 0.06)
        border.width: root.isActive ? 2 : 1
        border.color: root.isActive
                      ? Qt.rgba(root.alertColor.r,
                                root.alertColor.g,
                                root.alertColor.b, 0.50)
                      : Qt.rgba(Theme.Tokens.steel.r,
                                Theme.Tokens.steel.g,
                                Theme.Tokens.steel.b, 0.10)

        Behavior on color { ColorAnimation { duration: 200 } }
        Behavior on border.color { ColorAnimation { duration: 200 } }

        // Flash when active
        SequentialAnimation on opacity {
            running: root.isActive
            loops: Animation.Infinite
            NumberAnimation { to: 0.6; duration: 400 }
            NumberAnimation { to: 1.0; duration: 400 }
        }
        opacity: 1.0

        RowLayout {
            anchors.centerIn: parent
            spacing: 8

            // Direction arrow (left side)
            Text {
                visible: root.isActive && root.isLeft
                text: root.directionArrow
                font.pixelSize: 18
                color: root.alertColor

                Behavior on color { ColorAnimation { duration: 200 } }
            }

            // Alert label
            Text {
                text: root.isActive ? root.alertLabel : "NO ALERT"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: root.isActive ? 18 : 11
                font.weight: Font.Bold
                font.letterSpacing: root.isActive ? 2 : 1.2
                color: root.isActive ? root.alertColor : Theme.Tokens.steel
                opacity: root.isActive ? 1.0 : 0.4

                Behavior on color { ColorAnimation { duration: 200 } }
            }

            // Car number badge
            Rectangle {
                visible: root.isActive && root.carNumber.length > 0
                width: numText.implicitWidth + 12
                height: 22
                radius: 4
                color: Qt.rgba(root.alertColor.r,
                               root.alertColor.g,
                               root.alertColor.b, 0.20)

                Text {
                    id: numText
                    anchors.centerIn: parent
                    text: "#" + root.carNumber
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: root.alertColor
                }
            }

            // Direction arrow (right side)
            Text {
                visible: root.isActive && !root.isLeft
                text: root.directionArrow
                font.pixelSize: 18
                color: root.alertColor

                Behavior on color { ColorAnimation { duration: 200 } }
            }
        }
    }
}
