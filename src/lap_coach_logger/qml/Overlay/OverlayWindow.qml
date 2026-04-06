import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "../Theme" as Theme

Window {
    id: overlayRoot

    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "transparent"
    width: 380
    height: 220
    visible: false  // controlled externally

    OverlayContent {
        anchors.fill: parent
    }

    // Drag support
    MouseArea {
        anchors.fill: parent
        property point clickPos

        onPressed: function(mouse) {
            clickPos = Qt.point(mouse.x, mouse.y)
        }

        onPositionChanged: function(mouse) {
            overlayRoot.x += mouse.x - clickPos.x
            overlayRoot.y += mouse.y - clickPos.y
        }
    }
}
