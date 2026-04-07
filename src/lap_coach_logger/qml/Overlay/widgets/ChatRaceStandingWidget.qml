import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  ChatRaceStandingWidget -- viewer race prediction standings (260x240).
    Streaming leaderboard with rank, user, points, and win streak.
    Category: streaming -- uses racingPurple accent.                       */
Rectangle {
    id: root
    width: 260
    height: 240
    color: "transparent"

    // -- public API ----------------------------------------------------------
    // [{rank: int, user: string, points: int, streak: int}]
    property var standings: []
    property int roundNumber: 1

    // -- internal ------------------------------------------------------------
    readonly property var  _safeStandings: Array.isArray(standings)
                                           ? standings : []
    readonly property int  _count: _safeStandings.length

    // podium colours
    readonly property color _goldColor:   Theme.Tokens.pitOrange   // 1st
    readonly property color _silverColor: Theme.Tokens.steel       // 2nd
    readonly property color _bronzeColor: "#CD7F32"                // 3rd

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: Theme.Tokens.sm
            bottomMargin: Theme.Tokens.sm
            leftMargin: Theme.Tokens.md - 2
            rightMargin: Theme.Tokens.md - 2
        }
        spacing: 0

        // -- Header ----------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.Tokens.xs + 2

            Text {
                text: "PREDICTIONS"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            // Round badge
            Rectangle {
                implicitWidth: roundLbl.implicitWidth + Theme.Tokens.sm
                implicitHeight: 14
                radius: 3
                color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.15)
                border.width: 1
                border.color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.30)

                Text {
                    id: roundLbl
                    anchors.centerIn: parent
                    text: "RD " + Math.max(1, root.roundNumber || 1)
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    font.weight: Font.Bold
                    color: Theme.Tokens.racingPurple
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root._count + " players"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                color: Theme.Tokens.steel
                opacity: 0.6
            }
        }

        // -- Separator -------------------------------------------------------
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.Tokens.xs + 2
            Rectangle {
                anchors.centerIn: parent
                width: parent.width; height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5;
                                   color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.12) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // -- Column headers --------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.Tokens.xs

            ColumnHeader { text: "#";      preferredW: 20 }
            ColumnHeader { text: "PLAYER"; fillW: true    }
            ColumnHeader { text: "PTS";    preferredW: 32; hAlign: Text.AlignRight }
            ColumnHeader { text: "STREAK"; preferredW: 40; hAlign: Text.AlignRight }
        }

        // -- Empty state -----------------------------------------------------
        Text {
            visible: root._count === 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            text: "No standings yet"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.microSize
            color: Theme.Tokens.steel
            opacity: 0.5
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        // -- Standings list --------------------------------------------------
        ListView {
            id: standingsList
            visible: root._count > 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 2
            model: root._count

            delegate: StandingRow {
                required property int index
                width: standingsList.width
                row: root._safeStandings[index] || ({})
                rowIndex: index
            }
        }
    }

    // -- ColumnHeader component (de-duplicated header text) ------------------
    component ColumnHeader: Text {
        property int  preferredW: -1
        property bool fillW: false
        property int  hAlign: Text.AlignLeft

        Layout.preferredWidth: preferredW > 0 ? preferredW : undefined
        Layout.fillWidth: fillW
        horizontalAlignment: hAlign
        font.family: Theme.Typography.monoFamily
        font.pixelSize: 7
        font.weight: Font.Bold
        color: Theme.Tokens.steel
        opacity: 0.5
    }

    // -- StandingRow component (extracted delegate) ---------------------------
    component StandingRow: Rectangle {
        property var row: ({})
        property int rowIndex: 0

        height: 22
        radius: Theme.Tokens.xs
        color: rowIndex % 2 === 0
            ? Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.04)
            : "transparent"

        readonly property int    _rank:   (row && row.rank !== undefined)
                                          ? row.rank : (rowIndex + 1)
        readonly property string _user:   (row && row.user)   || ""
        readonly property int    _points: (row && row.points !== undefined)
                                          ? row.points : 0
        readonly property int    _streak: (row && row.streak !== undefined)
                                          ? row.streak : 0

        RowLayout {
            anchors { fill: parent; leftMargin: Theme.Tokens.xs; rightMargin: Theme.Tokens.xs }
            spacing: Theme.Tokens.xs

            // Rank -- podium colours for top 3
            Text {
                text: _rank
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Font.Bold
                color: rowIndex === 0 ? root._goldColor
                     : rowIndex === 1 ? root._silverColor
                     : rowIndex === 2 ? root._bronzeColor
                     : Theme.Tokens.chalk
                Layout.preferredWidth: 20
            }

            Text {
                text: _user
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                color: Theme.Tokens.chalk
                Layout.fillWidth: true
                elide: Text.ElideRight
            }

            Text {
                text: _points
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Font.Bold
                color: Theme.Tokens.racingPurple
                Layout.preferredWidth: 32
                horizontalAlignment: Text.AlignRight
            }

            Text {
                text: _streak > 0 ? _streak + "W" : "-"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                color: _streak > 0 ? Theme.Tokens.acidGreen : Theme.Tokens.steel
                Layout.preferredWidth: 40
                horizontalAlignment: Text.AlignRight
                opacity: _streak > 0 ? 1.0 : 0.4
            }
        }
    }
}
