import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  HeadToHeadWidget — driver comparison panel (300 x 160).
    Side-by-side comparison of two drivers showing sector
    times, lap times, and speed.                                */
Rectangle {
    id: root
    width: 300
    height: 160
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    // {name, time, sectors: [s1, s2, s3], speed}
    property var driver1: ({name: "", time: "", sectors: [], speed: 0})
    property var driver2: ({name: "", time: "", sectors: [], speed: 0})

    function fasterColor(v1, v2) {
        if (v1 === v2 || v1 === "" || v2 === "") return Theme.Tokens.chalk
        return v1 < v2 ? Theme.Tokens.acidGreen : Theme.Tokens.safetyRed
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 12
            rightMargin: 12
        }
        spacing: 6

        // ── Header ─────────────────────────────────────────────────
        Text {
            text: "HEAD TO HEAD"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 9
            font.weight: Font.Bold
            font.letterSpacing: 1.2
            color: Theme.Tokens.steel
        }

        // ── Driver names row ───────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            Text {
                Layout.fillWidth: true
                text: (root.driver1 && root.driver1.name) || "Driver 1"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 12
                font.weight: Font.Bold
                color: Theme.Tokens.acidGreen
                elide: Text.ElideRight
            }

            Text {
                text: "VS"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1
                color: Theme.Tokens.steel
                opacity: 0.5
            }

            Text {
                Layout.fillWidth: true
                text: (root.driver2 && root.driver2.name) || "Driver 2"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 12
                font.weight: Font.Bold
                color: Theme.Tokens.pitOrange
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideRight
            }
        }

        // ── Separator ──────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Qt.rgba(Theme.Tokens.chalk.r,
                           Theme.Tokens.chalk.g,
                           Theme.Tokens.chalk.b, 0.06)
        }

        // ── Lap time comparison ────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            Text {
                Layout.fillWidth: true
                text: (root.driver1 && root.driver1.time) || "--:--.---"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 14
                font.weight: Font.Bold
                color: {
                    var t1 = root.driver1 ? root.driver1.time : ""
                    var t2 = root.driver2 ? root.driver2.time : ""
                    return root.fasterColor(t1, t2)
                }
            }

            Text {
                text: "LAP"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 1
                color: Theme.Tokens.steel
                opacity: 0.5
            }

            Text {
                Layout.fillWidth: true
                text: (root.driver2 && root.driver2.time) || "--:--.---"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 14
                font.weight: Font.Bold
                horizontalAlignment: Text.AlignRight
                color: {
                    var t1 = root.driver1 ? root.driver1.time : ""
                    var t2 = root.driver2 ? root.driver2.time : ""
                    return root.fasterColor(t2, t1)
                }
            }
        }

        // ── Sector comparisons ─────────────────────────────────────
        Repeater {
            model: 3

            RowLayout {
                required property int index

                Layout.fillWidth: true
                spacing: 0

                readonly property var s1: {
                    var sectors = root.driver1 ? root.driver1.sectors : []
                    return sectors && index < sectors.length
                           ? sectors[index] : ""
                }
                readonly property var s2: {
                    var sectors = root.driver2 ? root.driver2.sectors : []
                    return sectors && index < sectors.length
                           ? sectors[index] : ""
                }

                Text {
                    Layout.fillWidth: true
                    text: s1 !== "" ? s1.toString() : "--.---"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 10
                    color: root.fasterColor(s1, s2)
                }

                Text {
                    text: "S" + (index + 1)
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 8
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                    color: Theme.Tokens.steel
                    opacity: 0.5
                }

                Text {
                    Layout.fillWidth: true
                    text: s2 !== "" ? s2.toString() : "--.---"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 10
                    horizontalAlignment: Text.AlignRight
                    color: root.fasterColor(s2, s1)
                }
            }
        }

        // ── Speed comparison ───────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            readonly property real spd1: root.driver1 ? (root.driver1.speed || 0) : 0
            readonly property real spd2: root.driver2 ? (root.driver2.speed || 0) : 0

            Text {
                Layout.fillWidth: true
                text: parent.spd1 > 0 ? parent.spd1.toFixed(0) + " kph" : "-- kph"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 10
                color: parent.spd1 >= parent.spd2
                       ? Theme.Tokens.acidGreen
                       : Theme.Tokens.safetyRed
            }

            Text {
                text: "SPD"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 0.8
                color: Theme.Tokens.steel
                opacity: 0.5
            }

            Text {
                Layout.fillWidth: true
                text: parent.spd2 > 0 ? parent.spd2.toFixed(0) + " kph" : "-- kph"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 10
                horizontalAlignment: Text.AlignRight
                color: parent.spd2 >= parent.spd1
                       ? Theme.Tokens.acidGreen
                       : Theme.Tokens.safetyRed
            }
        }
    }
}
