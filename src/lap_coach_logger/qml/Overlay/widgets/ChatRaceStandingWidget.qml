import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  ChatRaceStandingWidget — viewer race prediction standings (260x240).
    Streaming leaderboard with rank, user, points, and win streak.
    Category: streaming — uses racingPurple accent.                       */
Rectangle {
    id: root
    width: 260
    height: 240
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    // [{rank: int, user: string, points: int, streak: int}]
    property var standings: [
        { rank: 1, user: "Viewer1", points: 42, streak: 3 },
        { rank: 2, user: "Viewer2", points: 35, streak: 1 },
        { rank: 3, user: "Viewer3", points: 28, streak: 0 }
    ]
    property int roundNumber: 1

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 8
            bottomMargin: 8
            leftMargin: 10
            rightMargin: 10
        }
        spacing: 0

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

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
                implicitWidth: roundLbl.implicitWidth + 8
                implicitHeight: 14
                radius: 3
                color: Qt.rgba(Theme.Tokens.racingPurple.r,
                               Theme.Tokens.racingPurple.g,
                               Theme.Tokens.racingPurple.b, 0.15)
                border.width: 1
                border.color: Qt.rgba(Theme.Tokens.racingPurple.r,
                                      Theme.Tokens.racingPurple.g,
                                      Theme.Tokens.racingPurple.b, 0.30)

                Text {
                    id: roundLbl
                    anchors.centerIn: parent
                    text: "RD " + root.roundNumber
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    font.weight: Font.Bold
                    color: Theme.Tokens.racingPurple
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root.standings.length + " players"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                color: Theme.Tokens.steel
                opacity: 0.6
            }
        }

        // ── Separator ──────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 6
            Rectangle {
                anchors.centerIn: parent
                width: parent.width; height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5; color: Qt.rgba(Theme.Tokens.racingPurple.r,
                                                                  Theme.Tokens.racingPurple.g,
                                                                  Theme.Tokens.racingPurple.b, 0.12) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // ── Column headers ─────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 4

            Text {
                text: "#"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 7; font.weight: Font.Bold
                color: Theme.Tokens.steel; opacity: 0.5
                Layout.preferredWidth: 20
            }
            Text {
                text: "PLAYER"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 7; font.weight: Font.Bold
                color: Theme.Tokens.steel; opacity: 0.5
                Layout.fillWidth: true
            }
            Text {
                text: "PTS"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 7; font.weight: Font.Bold
                color: Theme.Tokens.steel; opacity: 0.5
                Layout.preferredWidth: 32
                horizontalAlignment: Text.AlignRight
            }
            Text {
                text: "STREAK"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 7; font.weight: Font.Bold
                color: Theme.Tokens.steel; opacity: 0.5
                Layout.preferredWidth: 40
                horizontalAlignment: Text.AlignRight
            }
        }

        // ── Standings list ─────────────────────────────────────────
        ListView {
            id: standingsList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 2
            model: root.standings.length

            delegate: Rectangle {
                required property int index
                width: standingsList.width
                height: 22
                radius: 4
                color: index % 2 === 0
                    ? Qt.rgba(Theme.Tokens.racingPurple.r,
                              Theme.Tokens.racingPurple.g,
                              Theme.Tokens.racingPurple.b, 0.04)
                    : "transparent"

                property var row: root.standings[index] || {}

                RowLayout {
                    anchors { fill: parent; leftMargin: 4; rightMargin: 4 }
                    spacing: 4

                    // Rank — podium colours
                    Text {
                        text: row.rank || (index + 1)
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 10
                        font.weight: Font.Bold
                        color: index === 0 ? Theme.Tokens.pitOrange
                             : index === 1 ? Theme.Tokens.steel
                             : index === 2 ? "#CD7F32"
                             : Theme.Tokens.chalk
                        Layout.preferredWidth: 20
                    }

                    Text {
                        text: row.user || ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 10
                        color: Theme.Tokens.chalk
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    Text {
                        text: row.points !== undefined ? row.points : ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 10
                        font.weight: Font.Bold
                        color: Theme.Tokens.racingPurple
                        Layout.preferredWidth: 32
                        horizontalAlignment: Text.AlignRight
                    }

                    Text {
                        text: (row.streak || 0) > 0 ? row.streak + "W" : "-"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 9
                        color: (row.streak || 0) > 0
                            ? Theme.Tokens.acidGreen
                            : Theme.Tokens.steel
                        Layout.preferredWidth: 40
                        horizontalAlignment: Text.AlignRight
                        opacity: (row.streak || 0) > 0 ? 1.0 : 0.4
                    }
                }
            }
        }
    }
}
