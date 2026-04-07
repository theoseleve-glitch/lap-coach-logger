import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  ChatRaceGameWidget — interactive race prediction game for streams (280x200).
    Shows prediction question, viewer entries, and results with points.
    Category: streaming — uses racingPurple accent.                          */
Rectangle {
    id: root
    width: 280
    height: 200
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    // [{user: string, pick: string, result: string, points: int}]
    property var    predictions: [
        { user: "Viewer1", pick: "P1 - VER", result: "correct", points: 10 },
        { user: "Viewer2", pick: "P1 - HAM", result: "wrong",   points: 0 },
        { user: "Viewer3", pick: "P1 - NOR", result: "",        points: 0 }
    ]
    property string question: "Who wins?"
    property bool   isActive: true

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
                text: "RACE GAME"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            // Active badge
            Rectangle {
                implicitWidth: activeLbl.implicitWidth + 8
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
                    id: activeLbl
                    anchors.centerIn: parent
                    text: root.isActive ? "LIVE" : "ENDED"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    font.weight: Font.Bold
                    color: Theme.Tokens.racingPurple
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root.predictions.length + " picks"
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

        // ── Question ───────────────────────────────────────────────
        Text {
            Layout.fillWidth: true
            text: root.question
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 12
            font.weight: Font.Bold
            color: Theme.Tokens.chalk
            elide: Text.ElideRight

            // Pulse while active
            SequentialAnimation on opacity {
                running: root.isActive
                loops: Animation.Infinite
                NumberAnimation { from: 1.0; to: 0.7; duration: 1200 }
                NumberAnimation { from: 0.7; to: 1.0; duration: 1200 }
            }
        }

        // ── Predictions list ───────────────────────────────────────
        ListView {
            id: predList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 2
            model: root.predictions.length

            delegate: RowLayout {
                required property int index
                width: predList.width
                spacing: 4

                property var entry: root.predictions[index] || {}

                Text {
                    text: entry.user || "???"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    color: Theme.Tokens.racingPurple
                    Layout.preferredWidth: 70
                    elide: Text.ElideRight
                }

                Text {
                    text: entry.pick || ""
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    color: Theme.Tokens.chalk
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }

                Text {
                    text: entry.result === "correct" ? "+" + entry.points
                        : entry.result === "wrong"   ? "0"
                        : "..."
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    color: entry.result === "correct" ? Theme.Tokens.acidGreen
                         : entry.result === "wrong"   ? Theme.Tokens.safetyRed
                         : Theme.Tokens.steel
                    Layout.preferredWidth: 28
                    horizontalAlignment: Text.AlignRight
                }
            }
        }
    }
}
