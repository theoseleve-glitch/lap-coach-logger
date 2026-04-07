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

    // Widget identity — set by OverlayWindow to link back to VM settings
    property string widgetId: ""

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
        border.width: (overlayVM && overlayVM.overlayLocked) ? 2 : 1
        border.color: (overlayVM && overlayVM.overlayLocked)
            ? Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.25)
            : Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.06)

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

    // Lock indicator — shown when overlays are locked
    Text {
        anchors { top: parent.top; right: parent.right; margins: 6 }
        text: "\uD83D\uDD12"
        font.pixelSize: 12
        color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.5)
        visible: overlayVM ? overlayVM.overlayLocked : false
        z: 10
    }

    // Drag support — grabs anywhere on the window
    MouseArea {
        anchors.fill: parent
        enabled: overlayVM ? !overlayVM.overlayLocked : true
        property point clickPos
        z: -1  // below content so widget buttons still work
        onPressed: function(mouse) { clickPos = Qt.point(mouse.x, mouse.y) }
        onPositionChanged: function(mouse) {
            root.x += mouse.x - clickPos.x
            root.y += mouse.y - clickPos.y
        }
        onReleased: {
            // Persist final position when drag ends
            if (root.widgetId && overlayVM) {
                overlayVM.setWidgetSetting(root.widgetId, "x", root.x)
                overlayVM.setWidgetSetting(root.widgetId, "y", root.y)
            }
        }
    }

    // Resize handle — bottom-right corner
    MouseArea {
        id: resizeHandle
        width: 16; height: 16
        anchors { right: parent.right; bottom: parent.bottom }
        cursorShape: Qt.SizeFDiagCursor
        visible: overlayVM ? !overlayVM.overlayLocked : true

        property point startPos
        property real startW
        property real startH

        onPressed: function(mouse) {
            startPos = Qt.point(mouse.x, mouse.y)
            startW = root.width
            startH = root.height
        }
        onPositionChanged: function(mouse) {
            var dx = mouse.x - startPos.x
            var dy = mouse.y - startPos.y
            root.width = Math.max(100, startW + dx)
            root.height = Math.max(60, startH + dy)
        }
        onReleased: {
            if (root.widgetId && overlayVM) {
                overlayVM.setWidgetSetting(root.widgetId, "width", Math.round(root.width))
                overlayVM.setWidgetSetting(root.widgetId, "height", Math.round(root.height))
            }
        }

        // Grip visual
        Rectangle {
            anchors { right: parent.right; bottom: parent.bottom; margins: 2 }
            width: 8; height: 8
            color: "transparent"
            // Three diagonal dots
            Column {
                anchors.fill: parent; spacing: 2
                Row { spacing: 2; Item{width:2;height:2} Item{width:2;height:2} Rectangle{width:2;height:2;radius:1;color:Qt.rgba(1,1,1,0.3)} }
                Row { spacing: 2; Item{width:2;height:2} Rectangle{width:2;height:2;radius:1;color:Qt.rgba(1,1,1,0.3)} Rectangle{width:2;height:2;radius:1;color:Qt.rgba(1,1,1,0.3)} }
                Row { spacing: 2; Rectangle{width:2;height:2;radius:1;color:Qt.rgba(1,1,1,0.3)} Rectangle{width:2;height:2;radius:1;color:Qt.rgba(1,1,1,0.3)} Rectangle{width:2;height:2;radius:1;color:Qt.rgba(1,1,1,0.3)} }
            }
        }
    }
}
