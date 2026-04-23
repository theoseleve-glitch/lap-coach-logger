import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  GapTimingWidget — gap to car ahead / behind (280 x 60).

    Two cells: "+1.2s P4" (ahead) and "-0.8s P6" (behind).
    Degraded rendering: if gap is missing (non-iRacing sims), cell
    shows "—" in steel rather than 0.0.                                   */
Rectangle {
    id: root

    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 280
    height: 60
    color: "transparent"

    // -- public API -------------------------------------------------------
    property real gapAhead: NaN        // seconds; NaN = no data
    property real gapBehind: NaN       // seconds; NaN = no data
    property int  positionAhead: 0
    property int  positionBehind: 0

    // -- helpers ----------------------------------------------------------
    function formatGap(seconds, hasData) {
        if (!hasData) return "\u2014"
        return "+" + seconds.toFixed(1) + "s"
    }

    function formatPos(n) {
        return n > 0 ? "P" + n : ""
    }

    readonly property bool hasAhead: !isNaN(gapAhead) && gapAhead > 0
    readonly property bool hasBehind: !isNaN(gapBehind) && gapBehind > 0

    // Background
    Rectangle {
        anchors.fill: parent
        radius: 8
        color: Qt.rgba(0, 0, 0, 0.78)
        border.width: 1
        border.color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g,
                              Theme.Tokens.chalk.b, 0.06)
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 1

        component GapCell: Item {
            property string label: ""
            property string pos: ""
            property string gap: ""
            property bool   active: true

            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                anchors.centerIn: parent
                spacing: 0

                Text {
                    text: parent.parent.label + (parent.parent.pos ? " " + parent.parent.pos : "")
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(8 * root.fontScale)
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                    color: Theme.Tokens.steel
                    opacity: 0.7
                    Layout.alignment: Qt.AlignHCenter
                }
                Text {
                    text: parent.parent.gap
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(18 * root.fontScale)
                    font.weight: Font.Bold
                    color: Theme.Tokens.chalk
                    opacity: parent.parent.active ? 1.0 : 0.4
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }

        GapCell {
            label: "AHEAD"
            pos: root.formatPos(root.positionAhead)
            gap: root.formatGap(root.gapAhead, root.hasAhead)
            active: root.hasAhead
        }
        Rectangle {
            width: 1; Layout.fillHeight: true; Layout.topMargin: 8; Layout.bottomMargin: 8
            color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08)
        }
        GapCell {
            label: "BEHIND"
            pos: root.formatPos(root.positionBehind)
            gap: root.formatGap(root.gapBehind, root.hasBehind)
            active: root.hasBehind
        }
    }
}
