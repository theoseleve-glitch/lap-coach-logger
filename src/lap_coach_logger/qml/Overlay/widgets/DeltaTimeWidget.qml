import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  DeltaTimeWidget — core timing overlay (310 px wide).
    Shows lap time, delta, sector jewels, best time, lap counter, and
    a sector-aware progress rail.                                      */
GlassSurface {
    id: root
    width: 310
    implicitHeight: col.implicitHeight + 24   // 12 top + 12 bottom

    // ── public API ──────────────────────────────────────────────────
    property real  delta: 0.0
    property string lapTime: "-:---.---"
    property string bestTime: "-:---.---"
    property int   lapNumber: 0
    property int   totalLaps: 0
    property real  lapProgress: 0          // 0-100
    property var   sectors: []             // [{id, delta, status}]

    // ── helpers ─────────────────────────────────────────────────────
    function deltaColor(d) {
        if (d < 0) return Theme.Tokens.acidGreen
        if (d > 0) return Theme.Tokens.safetyRed
        return Theme.Tokens.steel
    }

    function formatDelta(d) {
        if (d === 0) return "+0.000"
        var sign = d > 0 ? "+" : ""
        return sign + d.toFixed(3)
    }

    ColumnLayout {
        id: col
        anchors {
            fill: parent
            topMargin: 12
            bottomMargin: 12
            leftMargin: 14
            rightMargin: 14
        }
        spacing: 0

        // ── Row 1: Lap Time + Delta ────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            // Lap Time column
            ColumnLayout {
                spacing: 1
                Text {
                    text: "LAP TIME"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    font.letterSpacing: 1.2
                    color: Theme.Tokens.steel
                }
                Text {
                    text: root.lapTime
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 16
                    font.weight: Font.Bold
                    color: Theme.Tokens.chalk
                }
            }

            Item { Layout.fillWidth: true }

            // Delta column
            ColumnLayout {
                spacing: 1
                Layout.alignment: Qt.AlignRight
                Text {
                    text: "DELTA"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    font.letterSpacing: 1.2
                    color: Theme.Tokens.steel
                    horizontalAlignment: Text.AlignRight
                    Layout.fillWidth: true
                }
                Text {
                    text: formatDelta(root.delta)
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 20
                    font.weight: Font.Bold
                    color: deltaColor(root.delta)
                    horizontalAlignment: Text.AlignRight
                    Layout.fillWidth: true

                    Behavior on color { ColorAnimation { duration: 200 } }
                }
            }
        }

        // ── Sculpted divider ───────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 9
            Rectangle {
                anchors.centerIn: parent
                width: parent.width
                height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.3; color: Qt.rgba(Theme.Tokens.chalk.r,
                                                                  Theme.Tokens.chalk.g,
                                                                  Theme.Tokens.chalk.b, 0.06) }
                    GradientStop { position: 0.5; color: Qt.rgba(Theme.Tokens.racingPurple.r,
                                                                  Theme.Tokens.racingPurple.g,
                                                                  Theme.Tokens.racingPurple.b, 0.25) }
                    GradientStop { position: 0.7; color: Qt.rgba(Theme.Tokens.chalk.r,
                                                                  Theme.Tokens.chalk.g,
                                                                  Theme.Tokens.chalk.b, 0.06) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // ── Row 2: Sector jewels ───────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 4

            Repeater {
                model: 3
                delegate: sectorJewelComponent
            }
        }

        // ── Second divider ─────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 9
            Rectangle {
                anchors.centerIn: parent
                width: parent.width
                height: 1
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

        // ── Row 3: Best + Lap counter ──────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            ColumnLayout {
                spacing: 1
                Text {
                    text: "BST"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    font.letterSpacing: 1.2
                    color: Theme.Tokens.steel
                }
                Text {
                    text: root.bestTime
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 13
                    font.weight: Font.Bold
                    color: Theme.Tokens.chalk
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root.totalLaps > 0
                      ? "LAP " + root.lapNumber + "/" + root.totalLaps
                      : "LAP " + root.lapNumber
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
                Layout.alignment: Qt.AlignVCenter
            }
        }

        // ── Progress rail ──────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 10
            Layout.topMargin: 6

            // Track background
            Rectangle {
                id: progressTrack
                anchors {
                    left: parent.left
                    right: parent.right
                    verticalCenter: parent.verticalCenter
                }
                height: 3
                radius: 1.5
                color: Qt.rgba(Theme.Tokens.chalk.r,
                               Theme.Tokens.chalk.g,
                               Theme.Tokens.chalk.b, 0.06)

                // Filled portion
                Rectangle {
                    anchors {
                        left: parent.left
                        top: parent.top
                        bottom: parent.bottom
                    }
                    width: parent.width * Math.max(0, Math.min(1, root.lapProgress / 100))
                    radius: 1.5
                    color: Theme.Tokens.racingPurple

                    Behavior on width { NumberAnimation { duration: 80 } }
                }

                // Sector dividers at 33% and 66%
                Repeater {
                    model: 2
                    Rectangle {
                        required property int index
                        x: progressTrack.width * (index + 1) / 3 - 0.5
                        y: 0
                        width: 1
                        height: progressTrack.height
                        color: Qt.rgba(Theme.Tokens.racingPurple.r,
                                       Theme.Tokens.racingPurple.g,
                                       Theme.Tokens.racingPurple.b, 0.5)
                    }
                }
            }

            // Playhead dot
            Rectangle {
                id: playhead
                width: 7
                height: 7
                radius: 3.5
                color: Theme.Tokens.chalk
                x: progressTrack.x
                   + progressTrack.width * Math.max(0, Math.min(1, root.lapProgress / 100))
                   - 3.5
                anchors.verticalCenter: parent.verticalCenter

                Behavior on x { NumberAnimation { duration: 80 } }
            }
        }
    }

    // ── Sector Jewel delegate ──────────────────────────────────────
    Component {
        id: sectorJewelComponent

        GlassSurface {
            id: jewel
            required property int index

            readonly property var sectorData: {
                if (root.sectors && index < root.sectors.length)
                    return root.sectors[index]
                return { id: "S" + (index + 1), delta: 0, status: "pending" }
            }

            readonly property bool isActive:  sectorData.status === "active"
            readonly property bool isGain:    sectorData.status === "gain"
            readonly property bool isLoss:    sectorData.status === "loss"

            readonly property color tintColor: {
                if (isActive) return Theme.Tokens.racingPurple
                if (isGain)   return Theme.Tokens.acidGreen
                if (isLoss)   return Theme.Tokens.safetyRed
                return "transparent"
            }

            Layout.fillWidth: true
            implicitHeight: 38
            radius: 6
            surfaceAlpha: isActive ? 0.85 : 0.60
            borderAlpha: {
                if (isActive) return 0.16
                if (isGain || isLoss) return 0.10
                return 0.06
            }

            // Tint overlay
            Rectangle {
                anchors.fill: parent
                radius: jewel.radius
                color: Qt.rgba(jewel.tintColor.r,
                               jewel.tintColor.g,
                               jewel.tintColor.b,
                               isActive ? 0.04 : (isGain || isLoss) ? 0.03 : 0)
                Behavior on color { ColorAnimation { duration: 200 } }
            }

            RowLayout {
                anchors {
                    fill: parent
                    leftMargin: 6
                    rightMargin: 6
                }
                spacing: 3

                // Sector label
                Text {
                    text: "S" + (index + 1)
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    color: Theme.Tokens.racingPurple
                }

                // Apex dot
                Rectangle {
                    width: 3.5
                    height: 3.5
                    radius: 1.75
                    color: Theme.Tokens.racingPurple
                    opacity: isActive ? 1.0 : 0.4
                }

                Item { Layout.fillWidth: true }

                // Delta or placeholder
                Text {
                    text: {
                        if (isActive) return "\u2014.\u2014\u2014\u2014"
                        if (sectorData.delta !== undefined && sectorData.delta !== 0) {
                            var sign = sectorData.delta > 0 ? "+" : ""
                            return sign + sectorData.delta.toFixed(3)
                        }
                        return "\u2014.\u2014\u2014\u2014"
                    }
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 13
                    font.weight: Font.Bold
                    color: {
                        if (isGain) return Theme.Tokens.acidGreen
                        if (isLoss) return Theme.Tokens.safetyRed
                        return Theme.Tokens.steel
                    }
                    horizontalAlignment: Text.AlignRight

                    Behavior on color { ColorAnimation { duration: 200 } }
                }
            }
        }
    }
}
