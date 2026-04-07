import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  LaptimeLogWidget -- scrollable lap log table (280 x 200).
    Shows completed laps with time, delta, and status in a
    compact table layout.  Best lap highlighted with badge.         */
Rectangle {
    id: root
    width: 280
    height: 200
    color: "transparent"

    // -- public API -------------------------------------------------------
    property var laps: []   // list of {lap, time, delta, status}

    // -- helpers ----------------------------------------------------------
    readonly property int _lapCount: (laps && Array.isArray(laps)) ? laps.length : 0

    function _safeEntry(idx) {
        if (!laps || !Array.isArray(laps) || idx < 0 || idx >= laps.length)
            return null
        return laps[laps.length - 1 - idx]
    }

    function _isBest(entry) {
        return entry !== null && entry !== undefined
               && typeof entry.status === "string" && entry.status === "best"
    }

    function _statusColor(status) {
        if (typeof status !== "string") return Theme.Tokens.chalk
        switch (status) {
        case "best":     return Theme.Tokens.pitOrange
        case "improved": return Theme.Tokens.acidGreen
        case "slow":     return Theme.Tokens.safetyRed
        default:         return Theme.Tokens.chalk
        }
    }

    function _deltaColor(delta) {
        if (typeof delta !== "string" || delta.length === 0) return Theme.Tokens.steel
        if (delta.charAt(0) === "-") return Theme.Tokens.acidGreen
        if (delta.charAt(0) === "+") return Theme.Tokens.safetyRed
        return Theme.Tokens.steel
    }

    // -- inline header label component ------------------------------------
    component HeaderLabel: Text {
        property string label: ""
        text: label
        font.family: Theme.Typography.monoFamily
        font.pixelSize: 9
        font.weight: Font.Bold
        font.letterSpacing: 1.0
        color: Theme.Tokens.steel
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

        // -- Header row ---------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            HeaderLabel {
                label: "LAP"
                Layout.preferredWidth: 36
            }

            HeaderLabel {
                label: "TIME"
                Layout.fillWidth: true
            }

            HeaderLabel {
                label: "DELTA"
                horizontalAlignment: Text.AlignRight
                Layout.preferredWidth: 70
            }
        }

        // -- Divider ------------------------------------------------------
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 6
            Rectangle {
                anchors.centerIn: parent
                width: parent.width
                height: 1
                color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08)
            }
        }

        // -- Empty state --------------------------------------------------
        Text {
            visible: root._lapCount === 0
            text: "No laps recorded"
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: 11
            font.weight: Font.Normal
            color: Theme.Tokens.steel
            opacity: 0.6
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            Layout.topMargin: 20
        }

        // -- Scrollable list ----------------------------------------------
        ListView {
            id: lapList
            visible: root._lapCount > 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 1

            model: root._lapCount

            delegate: Rectangle {
                required property int index

                readonly property var entry: root._safeEntry(index)
                readonly property bool isBest: root._isBest(entry)

                width: lapList.width
                height: 22
                radius: 3

                // Best lap: pitOrange tinted background
                // Otherwise: alternating subtle stripes
                color: isBest
                       ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.10)
                       : (index % 2 === 0
                          ? Theme.Tokens.subtle(Theme.Tokens.chalk, 0.02)
                          : "transparent")

                border.width: isBest ? 1 : 0
                border.color: isBest
                              ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.20)
                              : "transparent"

                Behavior on color { ColorAnimation { duration: 200 } }

                RowLayout {
                    anchors {
                        fill: parent
                        leftMargin: 4
                        rightMargin: 4
                    }
                    spacing: 0

                    // Lap number
                    Text {
                        text: entry ? ("" + entry.lap) : ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: Theme.Tokens.steel
                        Layout.preferredWidth: 32
                    }

                    // "BEST" badge
                    Rectangle {
                        visible: isBest
                        implicitWidth: bestLabel.implicitWidth + 6
                        implicitHeight: 12
                        radius: 3
                        color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.18)

                        Text {
                            id: bestLabel
                            anchors.centerIn: parent
                            text: "BEST"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: 7
                            font.weight: Font.Bold
                            font.letterSpacing: 0.8
                            color: Theme.Tokens.pitOrange
                        }

                        Layout.rightMargin: 4
                    }

                    // Time
                    Text {
                        text: entry ? (entry.time || "") : ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: entry ? root._statusColor(entry.status)
                                     : Theme.Tokens.chalk
                        Layout.fillWidth: true

                        Behavior on color { ColorAnimation { duration: 200 } }
                    }

                    // Delta
                    Text {
                        text: entry ? (entry.delta || "") : ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: entry ? root._deltaColor(entry.delta)
                                     : Theme.Tokens.steel
                        horizontalAlignment: Text.AlignRight
                        Layout.preferredWidth: 70

                        Behavior on color { ColorAnimation { duration: 200 } }
                    }
                }
            }
        }
    }
}
