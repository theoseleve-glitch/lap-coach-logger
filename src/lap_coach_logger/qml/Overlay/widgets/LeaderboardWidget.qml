import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  LeaderboardWidget -- race leaderboard overlay (260 x 280).
    Podium colors (P1 gold, P2 silver, P3 bronze), alternating row
    backgrounds, player row with acidGreen accent border + tinted bg,
    position badges, right-aligned mono gap column, header row, and
    empty state.                                                       */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 260
    height: 280
    color: "transparent"

    // -- public API ------------------------------------------------------
    // [{pos, name, gap, isPlayer}]
    property var entries: []

    // -- podium palette (not in Tokens -- spec-mandated hex) -------------
    readonly property color _gold:   "#FFD700"
    readonly property color _silver: "#C0C0C0"
    readonly property color _bronze: "#CD7F32"

    function _podiumColor(pos) {
        if (pos === 1) return root._gold
        if (pos === 2) return root._silver
        if (pos === 3) return root._bronze
        return "transparent"
    }

    function _podiumBadgeBg(pos) {
        var c = _podiumColor(pos)
        if (c === "transparent") return "transparent"
        return Qt.rgba(c.r, c.g, c.b, 0.18)
    }

    function _podiumTextColor(pos) {
        if (pos === 1) return root._gold
        if (pos === 2) return root._silver
        if (pos === 3) return root._bronze
        return Theme.Tokens.chalk
    }

    // -- safe entries accessor -------------------------------------------
    readonly property var _safeEntries: {
        var e = root.entries
        return (e && Array.isArray(e)) ? e : []
    }

    // -- inline component: single leaderboard row -----------------------
    component LeaderboardRow: Rectangle {
        id: _row

        required property var    modelData
        required property int    index

        // null-safe field extraction
        readonly property int    _pos:      (_row.modelData && _row.modelData.pos !== undefined)
                                             ? _row.modelData.pos : (_row.index + 1)
        readonly property string _name:     (_row.modelData && _row.modelData.name) || ""
        readonly property string _gap:      (_row.modelData && _row.modelData.gap)  || ""
        readonly property bool   _isPlayer: (_row.modelData && _row.modelData.isPlayer) === true

        width: ListView.view ? ListView.view.width : 0
        height: 28
        radius: Theme.Tokens.radiusSm

        // -- player accent left border -----------------------------------
        Rectangle {
            visible: _row._isPlayer
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: 3
            height: parent.height - 6
            radius: 1
            color: Theme.Tokens.acidGreen
        }

        // -- background: player tinted, alternating rows, or transparent -
        color: {
            if (_row._isPlayer)
                return Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.08)
            if (_row.index % 2 === 1)
                return Theme.Tokens.subtle(Theme.Tokens.chalk, 0.03)
            return "transparent"
        }

        Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }

        RowLayout {
            anchors {
                fill: parent
                leftMargin:  Theme.Tokens.xs + (_row._isPlayer ? 4 : 0)
                rightMargin: Theme.Tokens.sm
            }
            spacing: 0

            // Position badge
            Rectangle {
                Layout.preferredWidth:  24
                Layout.preferredHeight: 18
                radius: 3
                color: root._podiumBadgeBg(_row._pos)

                Text {
                    anchors.centerIn: parent
                    text: _row._pos > 0 ? _row._pos.toString() : ""
                    font.family:    Theme.Typography.monoFamily
                    font.pixelSize: Math.round(11 * root.fontScale)
                    font.weight:    Font.Bold
                    color: _row._isPlayer
                           ? Theme.Tokens.acidGreen
                           : root._podiumTextColor(_row._pos)
                }
            }

            Item { width: Theme.Tokens.sm }

            // Driver name
            Text {
                Layout.fillWidth: true
                text: _row._name
                font.family:    Theme.Typography.monoFamily
                font.pixelSize: Math.round(11 * root.fontScale)
                color: _row._isPlayer ? Theme.Tokens.acidGreen : Theme.Tokens.chalk
                elide: Text.ElideRight
            }

            // Gap (right-aligned mono)
            Text {
                Layout.preferredWidth: 64
                text: _row._gap
                font.family:    Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight:    Font.DemiBold
                color: _row._isPlayer ? Theme.Tokens.acidGreen : Theme.Tokens.pitOrange
                horizontalAlignment: Text.AlignRight
            }
        }
    }

    // -- main layout -----------------------------------------------------
    ColumnLayout {
        anchors {
            fill: parent
            topMargin:    Theme.Tokens.sm
            bottomMargin: Theme.Tokens.sm
            leftMargin:   Theme.Tokens.md
            rightMargin:  Theme.Tokens.md
        }
        spacing: Theme.Tokens.xs

        // -- Title -------------------------------------------------------
        Text {
            text: "LEADERBOARD"
            font.family:       Theme.Typography.monoFamily
            font.pixelSize:    Theme.Typography.microSize
            font.weight:       Font.Bold
            font.letterSpacing: Theme.Typography.microSpacing
            color: Theme.Tokens.steel
        }

        // -- Separator ---------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.Tokens.subtle(Theme.Tokens.chalk)
        }

        // -- Header row --------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.Tokens.xs
            Layout.rightMargin: Theme.Tokens.sm
            spacing: 0

            Item { Layout.preferredWidth: 24 }
            Item { width: Theme.Tokens.sm }

            Text {
                Layout.fillWidth: true
                text: "DRIVER"
                font.family:       Theme.Typography.monoFamily
                font.pixelSize:    Math.round(8 * root.fontScale)
                font.weight:       Font.Bold
                font.letterSpacing: 0.8
                color: Theme.Tokens.steel
                opacity: 0.5
            }

            Text {
                Layout.preferredWidth: 64
                text: "GAP"
                font.family:       Theme.Typography.monoFamily
                font.pixelSize:    Math.round(8 * root.fontScale)
                font.weight:       Font.Bold
                font.letterSpacing: 0.8
                color: Theme.Tokens.steel
                opacity: 0.5
                horizontalAlignment: Text.AlignRight
            }
        }

        // -- List / empty state ------------------------------------------
        Item {
            Layout.fillWidth:  true
            Layout.fillHeight: true

            // Empty state
            Text {
                anchors.centerIn: parent
                visible: root._safeEntries.length === 0
                text: "No entries"
                font.family:    Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.captionSize
                color: Theme.Tokens.steel
                opacity: 0.35
            }

            ListView {
                anchors.fill: parent
                clip: true
                spacing: 0
                visible: root._safeEntries.length > 0
                model: root._safeEntries

                delegate: LeaderboardRow {}
            }
        }
    }
}
