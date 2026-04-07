import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  StandingsWidget -- full race standings table (280 x 300).
    Position (with podium colours), driver name, gap to leader,
    last lap time, and class badge for each entry.                 */
Rectangle {
    id: root
    width:  280
    height: 300
    color: "transparent"

    // -- public API ------------------------------------------------------
    // [{pos: int, name: string, gap: string, lastLap: string,
    //   classColor: color, isPlayer: bool}]
    property var standings: []

    // -- null-safe list length -------------------------------------------
    readonly property int _count: {
        var list = root.standings
        return (list && typeof list.length === "number") ? list.length : 0
    }

    // -- podium colour helper -------------------------------------------
    function _podiumColor(pos) {
        if (pos === 1) return "#FFD700"   // gold
        if (pos === 2) return "#C0C0C0"   // silver
        if (pos === 3) return "#CD7F32"   // bronze
        return Theme.Tokens.chalk
    }

    // -- inline component: column header label ---------------------------
    component ColHeader: Text {
        required property string label
        font.family:       Theme.Typography.monoFamily
        font.pixelSize:    8
        font.weight:       Font.Bold
        font.letterSpacing: 0.8
        color:   Theme.Tokens.steel
        opacity: 0.5
        text:    label
    }

    // -- layout ----------------------------------------------------------
    ColumnLayout {
        anchors {
            fill: parent
            topMargin:    Theme.Tokens.md
            bottomMargin: Theme.Tokens.md
            leftMargin:   Theme.Tokens.md
            rightMargin:  Theme.Tokens.md
        }
        spacing: Theme.Tokens.xs

        // -- Title -------------------------------------------------------
        Text {
            text: "STANDINGS"
            font.family:       Theme.Typography.monoFamily
            font.pixelSize:    Theme.Typography.microSize
            font.weight:       Font.Bold
            font.letterSpacing: Theme.Typography.microSpacing
            color: Theme.Tokens.steel
        }

        // -- Column headers ----------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            ColHeader { Layout.preferredWidth: 24; label: "#" }
            ColHeader { Layout.fillWidth: true;    label: "DRIVER" }
            ColHeader { Layout.preferredWidth: 52; label: "GAP";
                        horizontalAlignment: Text.AlignRight }
            ColHeader { Layout.preferredWidth: 56; label: "LAST";
                        horizontalAlignment: Text.AlignRight }
        }

        // -- Separator ---------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.Tokens.subtle(Theme.Tokens.chalk)
        }

        // -- Empty state -------------------------------------------------
        Text {
            visible: root._count === 0
            Layout.fillWidth:  true
            Layout.fillHeight: true
            text: "No standings yet\u2026"
            font.family:    Theme.Typography.bodyFamily
            font.pixelSize: Theme.Typography.captionSize
            color:   Theme.Tokens.steel
            opacity: 0.4
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment:   Text.AlignVCenter
        }

        // -- List --------------------------------------------------------
        ListView {
            visible: root._count > 0
            Layout.fillWidth:  true
            Layout.fillHeight: true
            clip:    true
            spacing: 1
            model:   root.standings || []

            delegate: Rectangle {
                required property var modelData
                required property int index

                // -- null-safe reads from modelData ----------------------
                readonly property bool   _isPlayer:   modelData ? !!modelData.isPlayer : false
                readonly property string _name:        (modelData && modelData.name)    || ""
                readonly property string _gap:         (modelData && modelData.gap)     || ""
                readonly property string _lastLap:     (modelData && modelData.lastLap) || ""
                readonly property int    _pos:         (modelData && modelData.pos !== undefined)
                                                       ? modelData.pos : -1
                readonly property color  _classColor:  (modelData && modelData.classColor)
                                                       ? modelData.classColor : Theme.Tokens.steel

                width:  ListView.view ? ListView.view.width : 0
                height: 24
                radius: 3

                // Player highlight or alternating row tint
                color: _isPlayer
                       ? Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.10)
                       : (index % 2 === 1
                          ? Theme.Tokens.subtle(Theme.Tokens.chalk, 0.025)
                          : "transparent")

                Behavior on color { ColorAnimation { duration: Theme.Motion.hoverDuration } }

                RowLayout {
                    anchors {
                        fill: parent
                        leftMargin:  Theme.Tokens.xs
                        rightMargin: Theme.Tokens.xs
                    }
                    spacing: 0

                    // Position number (podium colours for P1-P3)
                    Text {
                        Layout.preferredWidth: 20
                        text: _pos >= 0 ? _pos.toString() : ""
                        font.family:    Theme.Typography.monoFamily
                        font.pixelSize: 11
                        font.weight:    Font.Bold
                        color: _isPlayer
                               ? Theme.Tokens.acidGreen
                               : root._podiumColor(_pos)

                        Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                    }

                    // Class badge (coloured dot)
                    Rectangle {
                        Layout.preferredWidth:  8
                        Layout.preferredHeight: 8
                        Layout.alignment: Qt.AlignVCenter
                        radius: 4
                        color:   _classColor
                        opacity: 0.85

                        Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                    }

                    Item { width: Theme.Tokens.xs }

                    // Driver name
                    Text {
                        Layout.fillWidth: true
                        text: _name
                        font.family:    Theme.Typography.monoFamily
                        font.pixelSize: 11
                        color: _isPlayer ? Theme.Tokens.acidGreen : Theme.Tokens.chalk
                        elide: Text.ElideRight
                    }

                    // Gap to leader
                    Text {
                        Layout.preferredWidth: 52
                        text: _gap
                        font.family:    Theme.Typography.monoFamily
                        font.pixelSize: 10
                        color: Theme.Tokens.pitOrange
                        horizontalAlignment: Text.AlignRight

                        Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                    }

                    // Last lap time
                    Text {
                        Layout.preferredWidth: 56
                        text: _lastLap
                        font.family:    Theme.Typography.monoFamily
                        font.pixelSize: 10
                        color: Theme.Tokens.steel
                        horizontalAlignment: Text.AlignRight
                    }
                }
            }
        }
    }
}
