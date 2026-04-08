import QtQuick
import QtQuick.Window
import QtQuick.Controls
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

    // Customization settings — applied from VM
    property real fontScale: 1.0
    property int borderRadius: 12
    property int refreshHz: 60

    // Content injected by parent
    default property alias content: contentArea.data

    // Refresh rate control — throttles content updates
    // Widgets that use Canvas requestPaint() will be gated by this timer
    property bool _refreshTick: true
    Timer {
        id: refreshTimer
        interval: root.refreshHz > 0 ? Math.round(1000 / root.refreshHz) : 16
        running: root.visible
        repeat: true
        onTriggered: { root._refreshTick = !root._refreshTick }
    }

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

    // Right-click context menu
    Menu {
        id: contextMenu

        background: Rectangle {
            implicitWidth: 200
            color: "#141519"
            border.width: 1
            border.color: Qt.rgba(0.94, 0.93, 0.90, 0.08)
            radius: 8
        }

        MenuItem {
            text: overlayVM && overlayVM.overlayLocked ? "Unlock Positions" : "Lock Positions"
            onTriggered: if (overlayVM) overlayVM.toggleOverlayLock()
            contentItem: Text {
                text: parent.text
                font.family: "Consolas"
                font.pixelSize: 11
                color: parent.highlighted ? "#F0EDE5" : "#949494"
            }
            background: Rectangle {
                color: parent.highlighted ? Qt.rgba(0.94, 0.93, 0.90, 0.06) : "transparent"
                radius: 4
            }
        }
        MenuItem {
            text: "Center on Screen"
            onTriggered: if (overlayVM && root.widgetId) overlayVM.centerWidget(root.widgetId)
            contentItem: Text {
                text: parent.text
                font.family: "Consolas"
                font.pixelSize: 11
                color: parent.highlighted ? "#F0EDE5" : "#949494"
            }
            background: Rectangle {
                color: parent.highlighted ? Qt.rgba(0.94, 0.93, 0.90, 0.06) : "transparent"
                radius: 4
            }
        }
        MenuItem {
            text: "Reset Size"
            onTriggered: if (overlayVM && root.widgetId) overlayVM.resetWidget(root.widgetId)
            contentItem: Text {
                text: parent.text
                font.family: "Consolas"
                font.pixelSize: 11
                color: parent.highlighted ? "#F0EDE5" : "#949494"
            }
            background: Rectangle {
                color: parent.highlighted ? Qt.rgba(0.94, 0.93, 0.90, 0.06) : "transparent"
                radius: 4
            }
        }
        MenuSeparator {
            contentItem: Rectangle {
                implicitHeight: 1
                color: Qt.rgba(0.94, 0.93, 0.90, 0.08)
            }
        }
        MenuItem {
            text: "Hide This Widget"
            onTriggered: if (overlayVM && root.widgetId) overlayVM.toggleWidget(root.widgetId)
            contentItem: Text {
                text: parent.text
                font.family: "Consolas"
                font.pixelSize: 11
                color: parent.highlighted ? "#F0EDE5" : "#949494"
            }
            background: Rectangle {
                color: parent.highlighted ? Qt.rgba(0.94, 0.93, 0.90, 0.06) : "transparent"
                radius: 4
            }
        }
        MenuItem {
            text: "Hide All Overlays"
            onTriggered: root.visible = false
            contentItem: Text {
                text: parent.text
                font.family: "Consolas"
                font.pixelSize: 11
                color: parent.highlighted ? "#F0EDE5" : "#949494"
            }
            background: Rectangle {
                color: parent.highlighted ? Qt.rgba(0.94, 0.93, 0.90, 0.06) : "transparent"
                radius: 4
            }
        }
    }

    // Glass surface container
    Rectangle {
        id: container
        anchors.fill: parent
        radius: root.borderRadius
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

        // Content area — fontScale is exposed as a context property
        // Individual widgets read it to adjust their font.pixelSize values
        Item {
            id: contentArea
            anchors.fill: parent
            property real fontScale: root.fontScale
        }
    }

    // Title bar — shows widget name on hover, hidden by default for clean look
    Rectangle {
        id: titleBar
        anchors { top: parent.top; left: parent.left; right: parent.right }
        height: 20
        radius: root.borderRadius
        color: Qt.rgba(0, 0, 0, 0.5)
        opacity: titleHoverArea.containsMouse || (overlayVM && overlayVM.overlayLocked) ? 0.9 : 0
        z: 10

        Behavior on opacity { NumberAnimation { duration: 150 } }

        Row {
            anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
            spacing: 6

            // Drag dots (grip indicator)
            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Repeater {
                    model: 2
                    Row {
                        spacing: 2
                        Repeater {
                            model: 3
                            Rectangle { width: 2; height: 2; radius: 1; color: Qt.rgba(1,1,1,0.3) }
                        }
                    }
                }
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: root.widgetId.replace(/_/g, " ").toUpperCase()
                font { family: Theme.Typography.monoFamily; pixelSize: 8; weight: Font.Bold; letterSpacing: 1 }
                color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.6)
                elide: Text.ElideRight
                width: parent.width - 40
            }

            Item { width: 1; Layout.fillWidth: true }

            // Lock icon
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: overlayVM && overlayVM.overlayLocked ? "\uD83D\uDD12" : ""
                font.pixelSize: 10
                color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.5)
            }
        }

        MouseArea {
            id: titleHoverArea
            anchors.fill: parent
            hoverEnabled: true
            propagateComposedEvents: true
            // Don't consume clicks — let them fall through to drag handler
            onPressed: function(mouse) { mouse.accepted = false }
        }
    }

    // Drag support — grabs anywhere on the window
    MouseArea {
        anchors.fill: parent
        enabled: overlayVM ? !overlayVM.overlayLocked : true
        property point clickPos
        z: -1  // below content so widget buttons still work
        onPressed: function(mouse) { clickPos = Qt.point(mouse.x, mouse.y) }
        onPositionChanged: function(mouse) {
            var newX = root.x + mouse.x - clickPos.x
            var newY = root.y + mouse.y - clickPos.y

            // Snap to screen edges (15px threshold)
            if (overlayVM && overlayVM.snapEnabled) {
                var snapThreshold = 15
                var screenW = Screen.width
                var screenH = Screen.height

                // Left edge
                if (Math.abs(newX) < snapThreshold) newX = 0
                // Right edge
                if (Math.abs(newX + root.width - screenW) < snapThreshold) newX = screenW - root.width
                // Top edge
                if (Math.abs(newY) < snapThreshold) newY = 0
                // Bottom edge
                if (Math.abs(newY + root.height - screenH) < snapThreshold) newY = screenH - root.height
            }

            root.x = newX
            root.y = newY
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
