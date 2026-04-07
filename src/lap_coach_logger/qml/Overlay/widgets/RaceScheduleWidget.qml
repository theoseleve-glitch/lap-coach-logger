import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  RaceScheduleWidget — upcoming race sessions display (300x240).
    Shows time, series name, duration for each event.
    Highlights the next upcoming session.                         */
Rectangle {
    id: root
    width: 300
    height: 240
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property var events: [
        { name: "Sprint Race",      time: "14:00", duration: "20 min", registrationEnd: "13:45", isNext: true },
        { name: "Feature Race",     time: "15:30", duration: "45 min", registrationEnd: "15:15", isNext: false },
        { name: "Endurance Series", time: "17:00", duration: "60 min", registrationEnd: "16:30", isNext: false }
    ]

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 12
            rightMargin: 12
        }
        spacing: 0

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "SCHEDULE"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            Rectangle {
                implicitWidth: evtCount.implicitWidth + 8
                implicitHeight: 14
                radius: 3
                color: Qt.rgba(Theme.Tokens.marshalYellow.r,
                               Theme.Tokens.marshalYellow.g,
                               Theme.Tokens.marshalYellow.b, 0.12)

                Text {
                    id: evtCount
                    anchors.centerIn: parent
                    text: root.events.length
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 7
                    font.weight: Font.Bold
                    color: Theme.Tokens.marshalYellow
                }
            }

            Item { Layout.fillWidth: true }
        }

        // ── Separator ──────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 8
            Rectangle {
                anchors.centerIn: parent
                width: parent.width; height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5; color: Qt.rgba(Theme.Tokens.chalk.r,
                                                                  Theme.Tokens.chalk.g,
                                                                  Theme.Tokens.chalk.b, 0.08) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // ── Event rows ─────────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 4

            Repeater {
                model: root.events.length

                delegate: Rectangle {
                    required property int index
                    Layout.fillWidth: true
                    Layout.preferredHeight: 50
                    radius: 6

                    property var evt: root.events[index] || {}
                    property bool isNext: evt.isNext || false

                    color: isNext
                           ? Qt.rgba(Theme.Tokens.acidGreen.r,
                                     Theme.Tokens.acidGreen.g,
                                     Theme.Tokens.acidGreen.b, 0.06)
                           : Qt.rgba(Theme.Tokens.chalk.r,
                                     Theme.Tokens.chalk.g,
                                     Theme.Tokens.chalk.b, 0.03)
                    border.width: isNext ? 1 : 0
                    border.color: Qt.rgba(Theme.Tokens.acidGreen.r,
                                          Theme.Tokens.acidGreen.g,
                                          Theme.Tokens.acidGreen.b, 0.20)

                    RowLayout {
                        anchors {
                            fill: parent
                            leftMargin: 10
                            rightMargin: 10
                        }
                        spacing: 8

                        // Time column
                        ColumnLayout {
                            spacing: 0
                            Layout.preferredWidth: 44

                            Text {
                                text: evt.time || "--:--"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: 13
                                font.weight: Font.Bold
                                color: isNext ? Theme.Tokens.acidGreen : Theme.Tokens.chalk
                            }
                            Text {
                                text: evt.duration || ""
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: 8
                                color: Theme.Tokens.steel
                            }
                        }

                        // Separator dot
                        Rectangle {
                            width: 3; height: 3; radius: 1.5
                            color: isNext ? Theme.Tokens.acidGreen : Theme.Tokens.steel
                            Layout.alignment: Qt.AlignVCenter
                            opacity: 0.5
                        }

                        // Name + registration end
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0

                            Text {
                                text: evt.name || ""
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                color: Theme.Tokens.chalk
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Text {
                                visible: (evt.registrationEnd || "").length > 0
                                text: "REG " + (evt.registrationEnd || "")
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: 7
                                font.letterSpacing: 0.6
                                color: Theme.Tokens.steel
                            }
                        }

                        // NEXT badge
                        Rectangle {
                            visible: isNext
                            implicitWidth: nextLbl.implicitWidth + 8
                            implicitHeight: 14
                            radius: 3
                            color: Qt.rgba(Theme.Tokens.acidGreen.r,
                                           Theme.Tokens.acidGreen.g,
                                           Theme.Tokens.acidGreen.b, 0.15)
                            Layout.alignment: Qt.AlignVCenter

                            Text {
                                id: nextLbl
                                anchors.centerIn: parent
                                text: "NEXT"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: 7
                                font.weight: Font.Bold
                                color: Theme.Tokens.acidGreen
                            }
                        }
                    }
                }
            }
        }
    }
}
