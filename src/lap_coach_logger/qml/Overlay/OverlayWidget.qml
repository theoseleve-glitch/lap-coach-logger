import QtQuick
import QtQuick.Window
import "../Theme" as Theme

Window {
    id: root

    // Each overlay widget is its own frameless, draggable, always-on-top window
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "transparent"
    visible: false

    // Content injected by parent
    default property alias content: contentArea.data

    // Glass surface container
    Rectangle {
        id: container
        anchors.fill: parent
        radius: 12
        color: Qt.rgba(0, 0, 0, 0.78)
        border.width: 1
        border.color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.06)

        // Top refraction highlight
        Rectangle {
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 1
            radius: 12
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.3; color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.09) }
                GradientStop { position: 0.7; color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.09) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }

        // Content area
        Item {
            id: contentArea
            anchors.fill: parent
        }
    }

    // Drag anywhere
    MouseArea {
        anchors.fill: parent
        property point clickPos
        z: -1 // below content so buttons still work
        onPressed: function(mouse) { clickPos = Qt.point(mouse.x, mouse.y) }
        onPositionChanged: function(mouse) {
            root.x += mouse.x - clickPos.x
            root.y += mouse.y - clickPos.y
        }
    }
}
