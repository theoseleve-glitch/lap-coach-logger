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

    // Glass surface container — dims when not hovered for less distraction
    Rectangle {
        id: container
        anchors.fill: parent
        radius: root.borderRadius
        color: Qt.rgba(0, 0, 0, 0.78)
        opacity: dragArea.containsMouse ? 1.0 : 0.75
        Behavior on opacity { NumberAnimation { duration: 200 } }
        border.width: (overlayVM && overlayVM.overlayLocked) ? 2 : 1
        border.color: {
            // Session-state border glow
            if (overlayVM && overlayVM.overlayLocked)
                return Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.25)
            if (!overlayVM) return Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.06)
            var flag = overlayVM.currentFlag || ""
            if (flag === "red" || flag === "checkered")
                return Qt.rgba(Theme.Tokens.safetyRed.r, Theme.Tokens.safetyRed.g, Theme.Tokens.safetyRed.b, 0.3)
            if (flag === "yellow")
                return Qt.rgba(Theme.Tokens.marshalYellow.r, Theme.Tokens.marshalYellow.g, Theme.Tokens.marshalYellow.b, 0.25)
            if (overlayVM.isRecording)
                return Qt.rgba(Theme.Tokens.acidGreen.r, Theme.Tokens.acidGreen.g, Theme.Tokens.acidGreen.b, 0.12)
            return Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.06)
        }
        Behavior on border.color { ColorAnimation { duration: 400 } }

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
        opacity: titleHoverArea.containsMouse || dragArea.containsMouse || (overlayVM && overlayVM.overlayLocked) ? 0.9 : 0.3
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

            Item { width: 1 }

            // Lock icon
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: overlayVM && overlayVM.overlayLocked ? "\uD83D\uDD12" : ""
                font.pixelSize: 10
                color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.5)
                visible: overlayVM && overlayVM.overlayLocked
            }

            // Close button (X)
            Rectangle {
                width: 16; height: 16; radius: 8
                anchors.verticalCenter: parent.verticalCenter
                color: closeBtnArea.containsMouse
                       ? Qt.rgba(Theme.Tokens.safetyRed.r, Theme.Tokens.safetyRed.g, Theme.Tokens.safetyRed.b, 0.3)
                       : Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.1)

                Text {
                    anchors.centerIn: parent
                    text: "\u2715"
                    font.pixelSize: 9
                    color: closeBtnArea.containsMouse ? Theme.Tokens.safetyRed : Theme.Tokens.steel
                }

                MouseArea {
                    id: closeBtnArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (root.widgetId && overlayVM) {
                            overlayVM.toggleWidget(root.widgetId)
                        } else {
                            root.visible = false
                        }
                    }
                }
            }
        }

        // Title bar IS the drag handle
        MouseArea {
            id: titleHoverArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: overlayVM && overlayVM.overlayLocked ? Qt.ArrowCursor : Qt.SizeAllCursor
            enabled: overlayVM ? !overlayVM.overlayLocked : true
            property point clickPos
            onPressed: function(mouse) { clickPos = Qt.point(mouse.x, mouse.y) }
            onPositionChanged: function(mouse) {
                if (!pressed) return  // only drag when mouse button is held
                var newX = root.x + mouse.x - clickPos.x
                var newY = root.y + mouse.y - clickPos.y
                if (overlayVM && overlayVM.snapEnabled) {
                    var snapT = 15
                    var sW = Screen.width; var sH = Screen.height
                    if (Math.abs(newX) < snapT) newX = 0
                    if (Math.abs(newX + root.width - sW) < snapT) newX = sW - root.width
                    if (Math.abs(newY) < snapT) newY = 0
                    if (Math.abs(newY + root.height - sH) < snapT) newY = sH - root.height
                }
                root.x = newX; root.y = newY
            }
            onReleased: {
                if (root.widgetId && overlayVM) {
                    overlayVM.setWidgetSetting(root.widgetId, "x", root.x)
                    overlayVM.setWidgetSetting(root.widgetId, "y", root.y)
                }
            }
        }
    }

    // Hover detection for opacity boost (covers whole widget, doesn't consume events)
    MouseArea {
        id: dragArea
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.RightButton
        z: -1
        onClicked: function(mouse) {
            if (mouse.button === Qt.RightButton) contextMenu.popup()
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
