import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme

RowLayout {
    id: root

    property real throttle: 0.0
    property real brake: 0.0

    spacing: 6

    // Throttle bar
    Item {
        Layout.preferredWidth: 60
        Layout.preferredHeight: 6

        // Track
        Rectangle {
            anchors.fill: parent
            radius: Theme.Tokens.radiusSm / 2
            color: Qt.rgba(Theme.Tokens.acidGreen.r,
                           Theme.Tokens.acidGreen.g,
                           Theme.Tokens.acidGreen.b, 0.15)
        }

        // Fill
        Rectangle {
            anchors {
                left: parent.left
                top: parent.top
                bottom: parent.bottom
            }
            width: parent.width * Math.max(0, Math.min(1, root.throttle))
            radius: Theme.Tokens.radiusSm / 2
            color: Theme.Tokens.acidGreen

            Behavior on width {
                NumberAnimation { duration: 50 }
            }
        }
    }

    // Brake bar
    Item {
        Layout.preferredWidth: 60
        Layout.preferredHeight: 6

        // Track
        Rectangle {
            anchors.fill: parent
            radius: Theme.Tokens.radiusSm / 2
            color: Qt.rgba(Theme.Tokens.safetyRed.r,
                           Theme.Tokens.safetyRed.g,
                           Theme.Tokens.safetyRed.b, 0.15)
        }

        // Fill
        Rectangle {
            anchors {
                left: parent.left
                top: parent.top
                bottom: parent.bottom
            }
            width: parent.width * Math.max(0, Math.min(1, root.brake))
            radius: Theme.Tokens.radiusSm / 2
            color: Theme.Tokens.safetyRed

            Behavior on width {
                NumberAnimation { duration: 50 }
            }
        }
    }
}
