import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  CustomTextWidget -- customisable text banner for streams (280x60).
    Static or scrolling text with configurable size and colour.
    Category: streaming -- uses racingPurple accent.                     */
Rectangle {
    id: root
    width: 280
    height: 60
    color: "transparent"

    // -- public API ----------------------------------------------------------
    property string displayText: "YOUR TEXT HERE"
    property bool   scrolling: false
    property int    fontSize: 16
    property string textColor: ""

    // -- internal ------------------------------------------------------------
    readonly property string _safeText: (displayText || "").length > 0
                                        ? displayText : ""
    readonly property color  _color: textColor.length > 0
                                     ? textColor : Theme.Tokens.chalk

    // -- content -------------------------------------------------------------
    Rectangle {
        anchors.fill: parent
        radius: Theme.Tokens.radiusSm
        color: Qt.rgba(0, 0, 0, 0.55)
        border.width: 1
        border.color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.15)
        clip: true

        // -- Static text mode ------------------------------------------------
        Text {
            id: staticText
            visible: !root.scrolling
            anchors.centerIn: parent
            text: root._safeText
            font.family: Theme.Typography.monoFamily
            font.pixelSize: root.fontSize
            font.weight: Font.Bold
            color: root._color
            elide: Text.ElideRight
            width: parent.width - Theme.Tokens.xl - 4   // account for accent bar
            horizontalAlignment: Text.AlignHCenter

            Behavior on opacity {
                NumberAnimation { duration: 250; easing.type: Easing.InOutQuad }
            }
        }

        // -- Scrolling text mode ---------------------------------------------
        Item {
            visible: root.scrolling
            anchors.fill: parent
            clip: true

            Text {
                id: scrollText
                text: root._safeText + "          " + root._safeText
                font.family: Theme.Typography.monoFamily
                font.pixelSize: root.fontSize
                font.weight: Font.Bold
                color: root._color
                y: (parent.height - height) / 2

                NumberAnimation on x {
                    running: root.scrolling
                    loops: Animation.Infinite
                    from: 0
                    to: -scrollText.implicitWidth / 2
                    duration: Math.max(3000, root._safeText.length * 150)
                }
            }
        }

        // Subtle racingPurple edge accent
        Rectangle {
            anchors {
                left: parent.left; top: parent.top; bottom: parent.bottom
                leftMargin: 1
            }
            width: 2
            radius: 1
            color: Theme.Tokens.racingPurple
            opacity: 0.5
        }
    }
}
