import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme

RowLayout {
    id: root

    property var states: ["pending", "pending", "pending"]

    spacing: Theme.Tokens.xs

    Repeater {
        model: 3

        Rectangle {
            required property int index

            readonly property string sector: {
                if (root.states && index < root.states.length)
                    return root.states[index]
                return "pending"
            }

            readonly property color barColor: {
                switch (sector) {
                case "faster":  return Theme.Tokens.acidGreen
                case "slower":  return Theme.Tokens.safetyRed
                default:        return Qt.rgba(Theme.Tokens.chalk.r,
                                               Theme.Tokens.chalk.g,
                                               Theme.Tokens.chalk.b, 0.10)
                }
            }

            Layout.fillWidth: true
            height: 4
            radius: Theme.Tokens.radiusSm / 2
            color: barColor

            Behavior on color {
                ColorAnimation { duration: 200 }
            }
        }
    }
}
