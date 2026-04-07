import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  CustomTextWidget — customisable text banner for streams (280x60).
    Static or scrolling text with configurable size and colour.
    Category: streaming — uses racingPurple accent.                     */
Rectangle {
    id: root
    width: 280
    height: 60
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property string displayText: "YOUR TEXT HERE"
    property bool   scrolling: false
    property int    fontSize: 16
    property string textColor: Theme.Tokens.chalk.toString()

    // ── content ─────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        radius: 8
        color: Qt.rgba(0, 0, 0, 0.55)
        border.width: 1
        border.color: Qt.rgba(Theme.Tokens.racingPurple.r,
                              Theme.Tokens.racingPurple.g,
                              Theme.Tokens.racingPurple.b, 0.15)
        clip: true

        // ── Static text mode ────────────────────────────────────────
        Text {
            id: staticText
            visible: !root.scrolling
            anchors.centerIn: parent
            text: root.displayText
            font.family: Theme.Typography.monoFamily
            font.pixelSize: root.fontSize
            font.weight: Font.Bold
            color: root.textColor
            elide: Text.ElideRight
            width: parent.width - 20
            horizontalAlignment: Text.AlignHCenter
        }

        // ── Scrolling text mode ─────────────────────────────────────
        Item {
            visible: root.scrolling
            anchors.fill: parent
            clip: true

            Text {
                id: scrollText
                text: root.displayText + "          " + root.displayText
                font.family: Theme.Typography.monoFamily
                font.pixelSize: root.fontSize
                font.weight: Font.Bold
                color: root.textColor
                y: (parent.height - height) / 2

                NumberAnimation on x {
                    running: root.scrolling
                    loops: Animation.Infinite
                    from: 0
                    to: -scrollText.implicitWidth / 2
                    duration: Math.max(3000, root.displayText.length * 150)
                }
            }
        }

        // Subtle racingPurple edge accent
        Rectangle {
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom; leftMargin: 1 }
            width: 2
            radius: 1
            color: Theme.Tokens.racingPurple
            opacity: 0.5
        }
    }
}
