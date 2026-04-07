import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  LeaderboardWidget — simplified leaderboard (260 x 280).
    Alternating row backgrounds with position numbers, driver
    names, and gap to leader. Player row highlighted.            */
Rectangle {
    id: root
    width: 260
    height: 280
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    // [{pos, name, gap, isPlayer}]
    property var entries: []

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 12
            rightMargin: 12
        }
        spacing: 4

        // ── Header ─────────────────────────────────────────────────
        Text {
            text: "LEADERBOARD"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 9
            font.weight: Font.Bold
            font.letterSpacing: 1.2
            color: Theme.Tokens.steel
        }

        // Separator
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Qt.rgba(Theme.Tokens.chalk.r,
                           Theme.Tokens.chalk.g,
                           Theme.Tokens.chalk.b, 0.06)
        }

        // ── List ───────────────────────────────────────────────────
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 0
            model: root.entries || []

            delegate: Rectangle {
                required property var modelData
                required property int index

                width: ListView.view ? ListView.view.width : 0
                height: 26
                radius: 3

                color: {
                    if (modelData.isPlayer)
                        return Qt.rgba(Theme.Tokens.acidGreen.r,
                                       Theme.Tokens.acidGreen.g,
                                       Theme.Tokens.acidGreen.b, 0.08)
                    if (index % 2 === 1)
                        return Qt.rgba(Theme.Tokens.chalk.r,
                                       Theme.Tokens.chalk.g,
                                       Theme.Tokens.chalk.b, 0.03)
                    return "transparent"
                }

                RowLayout {
                    anchors {
                        fill: parent
                        leftMargin: 4
                        rightMargin: 6
                    }
                    spacing: 0

                    // Position badge
                    Rectangle {
                        Layout.preferredWidth: 24
                        Layout.preferredHeight: 18
                        radius: 3
                        color: {
                            if (modelData.pos === 1)
                                return Qt.rgba(Theme.Tokens.pitOrange.r,
                                               Theme.Tokens.pitOrange.g,
                                               Theme.Tokens.pitOrange.b, 0.20)
                            if (modelData.pos === 2)
                                return Qt.rgba(Theme.Tokens.steel.r,
                                               Theme.Tokens.steel.g,
                                               Theme.Tokens.steel.b, 0.15)
                            if (modelData.pos === 3)
                                return Qt.rgba(Theme.Tokens.pitOrange.r,
                                               Theme.Tokens.pitOrange.g,
                                               Theme.Tokens.pitOrange.b, 0.10)
                            return "transparent"
                        }

                        Text {
                            anchors.centerIn: parent
                            text: modelData.pos !== undefined
                                  ? modelData.pos.toString() : ""
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: {
                                if (modelData.isPlayer)
                                    return Theme.Tokens.acidGreen
                                if (modelData.pos <= 3)
                                    return Theme.Tokens.pitOrange
                                return Theme.Tokens.chalk
                            }
                        }
                    }

                    Item { width: 6 }

                    // Name
                    Text {
                        Layout.fillWidth: true
                        text: modelData.name || ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 11
                        color: modelData.isPlayer
                               ? Theme.Tokens.acidGreen
                               : Theme.Tokens.chalk
                        elide: Text.ElideRight
                    }

                    // Gap
                    Text {
                        Layout.preferredWidth: 60
                        text: modelData.gap || ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        color: modelData.isPlayer
                               ? Theme.Tokens.acidGreen
                               : Theme.Tokens.pitOrange
                        horizontalAlignment: Text.AlignRight
                    }
                }
            }
        }
    }
}
