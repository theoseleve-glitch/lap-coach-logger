import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  StandingsWidget — race standings table (280 x 300).
    Position, driver name, gap to leader, last lap time,
    and class badge for each entry.                             */
Rectangle {
    id: root
    width: 280
    height: 300
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    // [{pos, name, gap, lastLap, classColor, isPlayer}]
    property var standings: []

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
            text: "STANDINGS"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 9
            font.weight: Font.Bold
            font.letterSpacing: 1.2
            color: Theme.Tokens.steel
        }

        // ── Column headers ─────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            Text {
                Layout.preferredWidth: 24
                text: "#"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight: Font.Bold
                color: Theme.Tokens.steel
                opacity: 0.5
            }

            Text {
                Layout.fillWidth: true
                text: "DRIVER"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 0.8
                color: Theme.Tokens.steel
                opacity: 0.5
            }

            Text {
                Layout.preferredWidth: 52
                text: "GAP"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 0.8
                color: Theme.Tokens.steel
                opacity: 0.5
                horizontalAlignment: Text.AlignRight
            }

            Text {
                Layout.preferredWidth: 56
                text: "LAST"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 0.8
                color: Theme.Tokens.steel
                opacity: 0.5
                horizontalAlignment: Text.AlignRight
            }
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
            spacing: 1
            model: root.standings || []

            delegate: Rectangle {
                required property var modelData
                required property int index

                width: ListView.view ? ListView.view.width : 0
                height: 24
                radius: 3
                color: modelData.isPlayer
                       ? Qt.rgba(Theme.Tokens.acidGreen.r,
                                 Theme.Tokens.acidGreen.g,
                                 Theme.Tokens.acidGreen.b, 0.08)
                       : (index % 2 === 0
                          ? "transparent"
                          : Qt.rgba(Theme.Tokens.chalk.r,
                                    Theme.Tokens.chalk.g,
                                    Theme.Tokens.chalk.b, 0.02))

                RowLayout {
                    anchors {
                        fill: parent
                        leftMargin: 4
                        rightMargin: 4
                    }
                    spacing: 0

                    // Position number
                    Text {
                        Layout.preferredWidth: 20
                        text: modelData.pos !== undefined
                              ? modelData.pos.toString() : ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: modelData.isPlayer
                               ? Theme.Tokens.acidGreen
                               : Theme.Tokens.chalk
                    }

                    // Class badge
                    Rectangle {
                        Layout.preferredWidth: 3
                        Layout.preferredHeight: 14
                        radius: 1.5
                        color: modelData.classColor || Theme.Tokens.steel
                        opacity: 0.8
                    }

                    Item { width: 4 }

                    // Driver name
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
                        Layout.preferredWidth: 52
                        text: modelData.gap || ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 10
                        color: Theme.Tokens.pitOrange
                        horizontalAlignment: Text.AlignRight
                    }

                    // Last lap
                    Text {
                        Layout.preferredWidth: 56
                        text: modelData.lastLap || ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 10
                        color: Theme.Tokens.steel
                        horizontalAlignment: Text.AlignRight
                    }
                }
            }
        }
    }
}
