import QtQuick
import QtQuick.Controls
import "Theme" as Theme

ApplicationWindow {
    id: root
    visible: true
    width: 1180
    height: 760
    minimumWidth: 960
    minimumHeight: 640
    title: "Lap Coach Logger"
    color: Theme.Tokens.void_

    property bool forceClose: false

    AppShell {
        anchors.fill: parent
    }

    onClosing: function(close) {
        if (!forceClose) {
            close.accepted = false
            root.hide()
            if (typeof trayVM !== "undefined") {
                trayVM.showMessage("Running in tray. Use the tray icon to reopen or exit.")
            }
        }
    }
}
