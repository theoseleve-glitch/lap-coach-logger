import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  LaptimeLogWidget — scrollable lap log table (280 x 200).
    Shows completed laps with time, delta, and status in a
    compact table layout.                                        */
Rectangle {
    id: root
    width: 280
    height: 200
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property var laps: []   // list of {lap, time, delta, status}

    function statusColor(status) {
        switch (status) {
        case "best":     return Theme.Tokens.pitOrange
        case "improved": return Theme.Tokens.acidGreen
        case "slow":     return Theme.Tokens.safetyRed
        default:         return Theme.Tokens.chalk
        }
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 8
            leftMargin: 14
            rightMargin: 14
        }
        spacing: 0

        // ── Header row ─────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            Text {
                text: "LAP"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.0
                color: Theme.Tokens.steel
                Layout.preferredWidth: 36
            }

            Text {
                text: "TIME"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.0
                color: Theme.Tokens.steel
                Layout.fillWidth: true
            }

            Text {
                text: "DELTA"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.0
                color: Theme.Tokens.steel
                horizontalAlignment: Text.AlignRight
                Layout.preferredWidth: 70
            }
        }

        // ── Divider ────────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 6
            Rectangle {
                anchors.centerIn: parent
                width: parent.width
                height: 1
                color: Qt.rgba(Theme.Tokens.chalk.r,
                               Theme.Tokens.chalk.g,
                               Theme.Tokens.chalk.b, 0.08)
            }
        }

        // ── Scrollable list ────────────────────────────────────────
        ListView {
            id: lapList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 1

            model: root.laps.length

            delegate: Rectangle {
                required property int index

                readonly property var entry: root.laps[root.laps.length - 1 - index]

                width: lapList.width
                height: 22
                radius: 3
                color: index % 2 === 0
                       ? Qt.rgba(Theme.Tokens.chalk.r,
                                 Theme.Tokens.chalk.g,
                                 Theme.Tokens.chalk.b, 0.02)
                       : "transparent"

                RowLayout {
                    anchors {
                        fill: parent
                        leftMargin: 2
                        rightMargin: 2
                    }
                    spacing: 0

                    // Lap number
                    Text {
                        text: entry ? ("" + entry.lap) : ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: Theme.Tokens.steel
                        Layout.preferredWidth: 36
                    }

                    // Time
                    Text {
                        text: entry ? entry.time : ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: entry ? root.statusColor(entry.status) : Theme.Tokens.chalk
                        Layout.fillWidth: true
                    }

                    // Delta
                    Text {
                        text: entry ? entry.delta : ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: {
                            if (!entry || !entry.delta) return Theme.Tokens.steel
                            if (entry.delta.charAt(0) === "-") return Theme.Tokens.acidGreen
                            if (entry.delta.charAt(0) === "+") return Theme.Tokens.safetyRed
                            return Theme.Tokens.steel
                        }
                        horizontalAlignment: Text.AlignRight
                        Layout.preferredWidth: 70
                    }
                }
            }
        }
    }
}
