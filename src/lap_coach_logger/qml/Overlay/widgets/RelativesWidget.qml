import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  RelativesWidget -- relative-position list (280 x 240).
    Cars sorted by track position relative to player. Shows
    gap, driver name, class colour bar, and position.
    Player row highlighted with acidGreen accent.                 */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width:  280
    height: 240
    color: "transparent"

    // -- public API ------------------------------------------------------
    // [{position: int, name: string, gap: string, isPlayer: bool,
    //   classColor: color, gapSign: int (-1 behind, 0 self, +1 ahead)}]
    property var relatives: []

    // -- null-safe list length -------------------------------------------
    readonly property int _count: {
        var list = root.relatives
        return (list && typeof list.length === "number") ? list.length : 0
    }

    // -- inline component: column header label ---------------------------
    component ColHeader: Text {
        required property string label
        font.family:       Theme.Typography.monoFamily
        font.pixelSize:    Math.round(8 * root.fontScale)
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

        // -- Title row ---------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.Tokens.xs

            Text {
                text: "RELATIVE"
                font.family:       Theme.Typography.monoFamily
                font.pixelSize:    Theme.Typography.microSize
                font.weight:       Font.Bold
                font.letterSpacing: Theme.Typography.microSpacing
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root._count + " cars"
                font.family:    Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                color:   Theme.Tokens.steel
                opacity: 0.7
            }
        }

        // -- Column headers ----------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            ColHeader { Layout.preferredWidth: 28; label: "POS" }
            ColHeader { Layout.fillWidth: true;    label: "DRIVER" }
            ColHeader { Layout.preferredWidth: 60; label: "GAP";
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
            text: "Waiting for data\u2026"
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
            model:   root.relatives || []

            delegate: Rectangle {
                required property var modelData
                required property int index

                // -- null-safe reads from modelData ----------------------
                readonly property bool   _isPlayer:   modelData ? !!modelData.isPlayer : false
                readonly property string _name:        (modelData && modelData.name)    || ""
                readonly property string _gap:         (modelData && modelData.gap)     || ""
                readonly property int    _pos:         (modelData && modelData.position !== undefined)
                                                       ? modelData.position : -1
                readonly property color  _classColor:  (modelData && modelData.classColor)
                                                       ? modelData.classColor : Theme.Tokens.steel
                // gapSign: +1 = ahead of you (green), -1 = behind you (red), 0 = self
                readonly property int    _gapSign:     (modelData && modelData.gapSign !== undefined)
                                                       ? modelData.gapSign : 0

                readonly property color _gapColor: {
                    if (_isPlayer) return Theme.Tokens.acidGreen
                    if (_gapSign > 0) return Theme.Tokens.acidGreen
                    if (_gapSign < 0) return Theme.Tokens.safetyRed
                    return Theme.Tokens.pitOrange
                }

                width:  ListView.view ? ListView.view.width : 0
                height: 22
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

                    // Position
                    Text {
                        Layout.preferredWidth: 28
                        text: _pos >= 0 ? _pos.toString() : ""
                        font.family:    Theme.Typography.monoFamily
                        font.pixelSize: Math.round(11 * root.fontScale)
                        font.weight:    Font.Bold
                        color: _isPlayer ? Theme.Tokens.acidGreen : Theme.Tokens.chalk
                    }

                    // Class colour bar
                    Rectangle {
                        Layout.preferredWidth:  3
                        Layout.preferredHeight: 14
                        Layout.alignment: Qt.AlignVCenter
                        radius: 1.5
                        color:   _classColor
                        opacity: 0.85
                        Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                    }

                    Item { width: Theme.Tokens.xs + 2 }

                    // Driver name
                    Text {
                        Layout.fillWidth: true
                        text: _name
                        font.family:    Theme.Typography.monoFamily
                        font.pixelSize: Math.round(11 * root.fontScale)
                        color: _isPlayer ? Theme.Tokens.acidGreen : Theme.Tokens.chalk
                        elide: Text.ElideRight
                    }

                    // Gap (coloured by direction)
                    Text {
                        Layout.preferredWidth: 60
                        text: _gap
                        font.family:    Theme.Typography.monoFamily
                        font.pixelSize: Math.round(11 * root.fontScale)
                        font.weight:    Font.DemiBold
                        color: _gapColor
                        horizontalAlignment: Text.AlignRight

                        Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                    }
                }
            }
        }
    }
}
