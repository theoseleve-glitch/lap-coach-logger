import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  RaceStrategyWidget -- live race strategy overlay (280x200).
    Shows next pit lap, fuel to add, stints remaining,
    fuel at finish, and a mini timeline of pit stop positions.  */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 280
    height: 200
    color: "transparent"

    // -- public API --
    property int  nextPitLap: 0
    property real fuelToAdd: 0.0
    property int  stintsRemaining: 0
    property var  pitStops: []
    property real fuelAtFinish: 0.0
    property int  totalLaps: 0
    property int  currentLap: 0

    // -- helpers --
    function safeFix(v, d) { return isFinite(v) ? v.toFixed(d) : "--" }
    readonly property bool hasPit: nextPitLap > 0
    readonly property color finishColor: fuelAtFinish >= 0
                                         ? Theme.Tokens.acidGreen
                                         : Theme.Tokens.safetyRed
    readonly property string finishSign: fuelAtFinish >= 0 ? "+" : ""

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: Theme.Tokens.md
            bottomMargin: Theme.Tokens.md
            leftMargin: Theme.Tokens.md
            rightMargin: Theme.Tokens.md
        }
        spacing: 0

        // -- Header --
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "STRATEGY"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Theme.Typography.microWeight
                font.letterSpacing: Theme.Typography.microSpacing
                color: Theme.Tokens.steel
            }

            // Stops badge
            Rectangle {
                visible: root.hasPit
                implicitWidth: stopsBadgeLabel.implicitWidth + 10
                implicitHeight: 14
                radius: 3
                color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.12)
                border.width: 1
                border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.25)

                Text {
                    id: stopsBadgeLabel
                    anchors.centerIn: parent
                    text: root.stintsRemaining + " STOP" + (root.stintsRemaining !== 1 ? "S" : "")
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(7 * root.fontScale)
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                    color: Theme.Tokens.pitOrange
                }
            }

            // No-stop badge
            Rectangle {
                visible: !root.hasPit && root.totalLaps > 0
                implicitWidth: noStopLabel.implicitWidth + 10
                implicitHeight: 14
                radius: 3
                color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.12)
                border.width: 1
                border.color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.25)

                Text {
                    id: noStopLabel
                    anchors.centerIn: parent
                    text: "NO STOP"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(7 * root.fontScale)
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                    color: Theme.Tokens.acidGreen
                }
            }

            Item { Layout.fillWidth: true }
        }

        // -- Separator --
        GradientSep {}

        // -- Hero: next pit lap --
        Text {
            visible: root.hasPit
            text: "PIT LAP " + root.nextPitLap
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(22 * root.fontScale)
            font.weight: Font.Bold
            color: Theme.Tokens.pitOrange
            Layout.alignment: Qt.AlignLeft
            Layout.bottomMargin: 2

            Behavior on text {
                SequentialAnimation {
                    NumberAnimation { target: parent; property: "opacity"; to: 0.4; duration: 80 }
                    NumberAnimation { target: parent; property: "opacity"; to: 1.0; duration: 200 }
                }
            }
        }

        // -- Data rows --
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 5

            DataRow {
                visible: root.hasPit
                label: "FUEL TO ADD"
                value: root.safeFix(root.fuelToAdd, 1) + " L"
                valueColor: Theme.Tokens.pitOrange
                prominent: true
            }

            DataRow {
                label: "FUEL AT FINISH"
                value: root.finishSign + root.safeFix(root.fuelAtFinish, 1) + " L"
                valueColor: root.finishColor
            }
        }

        GradientSep {}

        // -- Mini timeline: horizontal bar with pit markers --
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 22
            visible: root.totalLaps > 0

            // Track bar background
            Rectangle {
                id: trackBar
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.right: parent.right
                height: 4
                radius: 2
                color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08)
            }

            // Progress fill
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                width: root.totalLaps > 0
                       ? trackBar.width * Math.min(1, root.currentLap / root.totalLaps)
                       : 0
                height: 4
                radius: 2
                color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.50)

                Behavior on width { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
            }

            // Pit stop markers
            Repeater {
                model: root.pitStops || []

                Rectangle {
                    required property var modelData
                    x: root.totalLaps > 0
                       ? trackBar.x + (modelData.lap / root.totalLaps) * trackBar.width - 3
                       : 0
                    anchors.verticalCenter: parent.verticalCenter
                    width: 6
                    height: 10
                    radius: 2
                    color: Theme.Tokens.pitOrange
                    opacity: modelData.lap > root.currentLap ? 1.0 : 0.35
                }
            }

            // Start label
            Text {
                anchors.left: parent.left
                anchors.top: trackBar.bottom
                anchors.topMargin: 1
                text: "0"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(7 * root.fontScale)
                color: Theme.Tokens.subtle(Theme.Tokens.steel, 0.6)
            }

            // End label
            Text {
                anchors.right: parent.right
                anchors.top: trackBar.bottom
                anchors.topMargin: 1
                text: root.totalLaps
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(7 * root.fontScale)
                color: Theme.Tokens.subtle(Theme.Tokens.steel, 0.6)
            }
        }

        Item { Layout.fillHeight: true }
    }

    // -- Gradient separator component --
    component GradientSep: Item {
        Layout.fillWidth: true
        Layout.preferredHeight: 8
        Rectangle {
            anchors.centerIn: parent
            width: parent.width; height: 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }
    }

    // -- Reusable data row --
    component DataRow: RowLayout {
        property string label
        property string value
        property color  valueColor: Theme.Tokens.chalk
        property bool   prominent: false

        Layout.fillWidth: true

        Text {
            text: label
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.microSize
            font.weight: Theme.Typography.microWeight
            font.letterSpacing: 1.0
            color: Theme.Tokens.steel
        }
        Item { Layout.fillWidth: true }
        Text {
            text: value
            font.family: Theme.Typography.monoFamily
            font.pixelSize: prominent ? Math.round(16 * root.fontScale) : Math.round(13 * root.fontScale)
            font.weight: Font.Bold
            color: valueColor
            Behavior on color     { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
            Behavior on font.pixelSize { NumberAnimation { duration: 150 } }
        }
    }
}
