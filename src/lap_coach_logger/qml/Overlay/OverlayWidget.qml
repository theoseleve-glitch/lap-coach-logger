import QtQuick
import QtQuick.Window
import "../Theme" as Theme

/*  OverlayWidget — frameless, always-on-top, draggable window wrapper.

    Designed for sim racing: stays above borderless-fullscreen games
    without stealing focus. On Windows, applies WS_EX_TOPMOST +
    WS_EX_NOACTIVATE + WS_EX_TOOLWINDOW via native API after show.

    Cross-platform: flags degrade gracefully on non-Windows.
*/
Window {
    id: root

    flags: Qt.FramelessWindowHint
         | Qt.WindowStaysOnTopHint
         | Qt.WindowDoesNotAcceptFocus
         | Qt.Tool

    color: "transparent"
    visible: false

    // Content injected by parent
    default property alias content: contentArea.data

    // Apply native overlay flags when window becomes visible
    onVisibleChanged: {
        if (visible && overlayVM) {
            // Small delay to let the window fully realize before calling native API
            applyFlagsTimer.start()
        }
    }

    Timer {
        id: applyFlagsTimer
        interval: 100
        repeat: false
        onTriggered: {
            if (root.visible && overlayVM) {
                // transientParent.winId() or root itself — get the native handle
                // In QML, Window doesn't directly expose HWND, but we can use
                // a workaround: the ViewModel applies flags by window title match
                overlayVM.applyOverlayFlags(0)  // 0 = apply to all overlay windows
            }
        }
    }

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

    // Drag support — grabs anywhere on the window
    MouseArea {
        anchors.fill: parent
        property point clickPos
        z: -1  // below content so widget buttons still work
        onPressed: function(mouse) { clickPos = Qt.point(mouse.x, mouse.y) }
        onPositionChanged: function(mouse) {
            root.x += mouse.x - clickPos.x
            root.y += mouse.y - clickPos.y
        }
    }
}
