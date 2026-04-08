import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  DeltaTimeWidget — premium timing overlay (310 px wide).
    Matches Figma: glass surface, sector jewels with tint,
    sculpted purple dividers, progress rail with playhead.

    Design reference: Figma Make delta-time-overlay
    - Atmosphere tint shifts green/red based on delta direction
    - Sector jewels show LIVE badge for active sector
    - Purple apex motif throughout (dividers, progress, dots)
*/
GlassSurface {
    id: root
    width: 310
    implicitHeight: col.implicitHeight + 28

    // ── Font scale — multiplies all font sizes (from parent or OverlayWidget) ──
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0

    // ── Public API ──────────────────────────────────────────────
    property real   delta: 0.0
    property string lapTime: "—:——.———"
    property string bestTime: "—:——.———"
    property int    lapNumber: 0
    property int    totalLaps: 0
    property real   lapProgress: 0          // 0–100
    property var    sectors: []             // [{id, delta, status}]

    // ── Atmosphere tint (green when gaining, red when losing) ──
    Rectangle {
        anchors.fill: parent
        radius: root.radius
        color: root.delta < -0.01
                 ? Qt.rgba(Theme.Tokens.acidGreen.r, Theme.Tokens.acidGreen.g, Theme.Tokens.acidGreen.b, 0.015)
               : root.delta > 0.01
                 ? Qt.rgba(Theme.Tokens.safetyRed.r, Theme.Tokens.safetyRed.g, Theme.Tokens.safetyRed.b, 0.015)
               : "transparent"
        Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
    }

    // ── Helpers ─────────────────────────────────────────────────
    function deltaColor(d) {
        if (d < -0.001) return Theme.Tokens.acidGreen
        if (d >  0.001) return Theme.Tokens.safetyRed
        return Theme.Tokens.steel
    }

    function formatDelta(d) {
        if (isNaN(d) || d === undefined || d === null) return "—.———"
        var sign = d >= 0 ? "+" : ""
        return sign + d.toFixed(3)
    }

    function safeSector(idx) {
        if (!root.sectors || idx >= root.sectors.length) {
            return { id: idx + 1, delta: 0, status: "pending" }
        }
        return root.sectors[idx] || { id: idx + 1, delta: 0, status: "pending" }
    }

    // ── Inline: sculpted divider with purple apex center ───────
    component SculptedDivider: Item {
        property real purpleIntensity: 0.25
        Layout.fillWidth: true
        Layout.preferredHeight: 10
        Rectangle {
            anchors.centerIn: parent
            width: parent.width
            height: 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.2; color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.05) }
                GradientStop { position: 0.5; color: Qt.rgba(Theme.Tokens.racingPurple.r, Theme.Tokens.racingPurple.g, Theme.Tokens.racingPurple.b, purpleIntensity) }
                GradientStop { position: 0.8; color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.05) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }
        // Apex dot at center
        Rectangle {
            anchors.centerIn: parent
            width: 2.5; height: 2.5; radius: 1.25
            color: Theme.Tokens.racingPurple
            opacity: 0.4
        }
    }

    ColumnLayout {
        id: col
        anchors {
            fill: parent
            topMargin: 14; bottomMargin: 0
            leftMargin: 16; rightMargin: 16
        }
        spacing: 0

        // ── Row 1: Lap Time + Delta ────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            ColumnLayout {
                spacing: 1
                Text {
                    text: "LAP TIME"
                    font { family: Theme.Typography.monoFamily; pixelSize: Math.round(9 * root.fontScale); weight: Font.Bold; letterSpacing: 2 }
                    color: Theme.Tokens.steel
                    lineHeight: 1
                }
                Text {
                    text: root.lapTime || "—:——.———"
                    font { family: Theme.Typography.monoFamily; pixelSize: Math.round(16 * root.fontScale); weight: Font.Bold }
                    color: Theme.Tokens.chalk
                    lineHeight: 1.3
                    Behavior on text { SequentialAnimation {
                        NumberAnimation { target: lapTimeText; property: "opacity"; to: 0.6; duration: 60 }
                        NumberAnimation { target: lapTimeText; property: "opacity"; to: 1.0; duration: 120 }
                    }}
                    id: lapTimeText
                }
            }

            Item { Layout.fillWidth: true }

            ColumnLayout {
                spacing: 1
                Layout.alignment: Qt.AlignRight
                Text {
                    text: "DELTA"
                    font { family: Theme.Typography.monoFamily; pixelSize: Math.round(9 * root.fontScale); weight: Font.Bold; letterSpacing: 2 }
                    color: Theme.Tokens.steel
                    horizontalAlignment: Text.AlignRight
                    Layout.fillWidth: true
                    lineHeight: 1
                }
                Text {
                    text: formatDelta(root.delta)
                    font { family: Theme.Typography.monoFamily; pixelSize: Math.round(20 * root.fontScale); weight: Font.Bold; letterSpacing: -0.5 }
                    color: deltaColor(root.delta)
                    horizontalAlignment: Text.AlignRight
                    Layout.fillWidth: true
                    lineHeight: 1.1
                    Behavior on color { ColorAnimation { duration: 200 } }
                }
            }
        }

        SculptedDivider { purpleIntensity: 0.20 }

        // ── Row 2: Sector jewels ───────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 5

            Repeater {
                model: 3
                delegate: GlassSurface {
                    id: jewel
                    required property int index

                    readonly property var sd: root.safeSector(index)
                    readonly property bool isActive: sd.status === "active"
                    readonly property bool isGain:   sd.status === "gain"
                    readonly property bool isLoss:   sd.status === "loss"
                    readonly property color tint:
                        isActive ? Theme.Tokens.racingPurple :
                        isGain   ? Theme.Tokens.acidGreen :
                        isLoss   ? Theme.Tokens.safetyRed : "transparent"

                    Layout.fillWidth: true
                    implicitHeight: 42
                    radius: 8
                    surfaceAlpha: isActive ? 0.85 : 0.55
                    borderAlpha: isActive ? 0.18 : (isGain || isLoss) ? 0.10 : 0.04

                    // State tint overlay
                    Rectangle {
                        anchors.fill: parent; radius: jewel.radius
                        color: Qt.rgba(jewel.tint.r, jewel.tint.g, jewel.tint.b,
                                       isActive ? 0.05 : (isGain || isLoss) ? 0.03 : 0)
                        Behavior on color { ColorAnimation { duration: 200 } }
                    }

                    ColumnLayout {
                        anchors { fill: parent; leftMargin: 8; rightMargin: 8; topMargin: 6; bottomMargin: 5 }
                        spacing: 2

                        // Header: S1 + apex dot + LIVE badge
                        RowLayout {
                            spacing: 4
                            Rectangle {
                                width: 3.5; height: 3.5; radius: 1.75
                                color: Theme.Tokens.racingPurple
                                opacity: isActive ? 1.0 : 0.35
                                // Glow for active
                                layer.enabled: isActive
                            }
                            Text {
                                text: "S" + (index + 1)
                                font { family: Theme.Typography.monoFamily; pixelSize: Math.round(9 * root.fontScale); weight: Font.Bold; letterSpacing: 1.5 }
                                color: Theme.Tokens.racingPurple
                                opacity: isActive ? 1.0 : 0.5
                            }
                            Item { Layout.fillWidth: true }
                            // LIVE badge for active sector
                            Text {
                                visible: isActive
                                text: "LIVE"
                                font { family: Theme.Typography.monoFamily; pixelSize: Math.round(7 * root.fontScale); weight: Font.Bold; letterSpacing: 1.5 }
                                color: Theme.Tokens.racingPurple
                                opacity: 0.6
                            }
                        }

                        // Delta value
                        Text {
                            text: {
                                if (isActive) return "—.———"
                                var d = sd.delta || 0
                                if (d === 0) return "—.———"
                                return (d > 0 ? "+" : "") + d.toFixed(3)
                            }
                            font { family: Theme.Typography.monoFamily; pixelSize: Math.round(13 * root.fontScale); weight: Font.Bold; letterSpacing: -0.3 }
                            color: isGain ? Theme.Tokens.acidGreen :
                                   isLoss ? Theme.Tokens.safetyRed :
                                   Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.25)
                            lineHeight: 1
                            Behavior on color { ColorAnimation { duration: 200 } }
                        }
                    }
                }
            }
        }

        SculptedDivider { purpleIntensity: 0.12 }

        // ── Row 3: Best time + Lap counter ─────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            Text {
                text: "BST " + (root.bestTime || "—:——.———")
                font { family: Theme.Typography.monoFamily; pixelSize: Math.round(9 * root.fontScale); weight: Font.Bold; letterSpacing: 1.5 }
                color: Theme.Tokens.steel
                opacity: 0.7
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root.totalLaps > 0
                      ? "LAP " + root.lapNumber + " / " + root.totalLaps
                      : "LAP " + root.lapNumber
                font { family: Theme.Typography.monoFamily; pixelSize: Math.round(9 * root.fontScale); weight: Font.Bold; letterSpacing: 1.5 }
                color: Theme.Tokens.steel
                opacity: 0.5
            }
        }

        // Spacer before progress
        Item { Layout.preferredHeight: 10 }
    }

    // ── Progress rail (outside ColumnLayout for full-width bleed) ──
    Item {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 3

        // Track base
        Rectangle {
            id: progressTrack
            anchors.fill: parent
            color: Qt.rgba(0.08, 0.08, 0.08, 0.9)
            border.width: 1
            border.color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.03)

            // Filled portion with sector-aware coloring
            Rectangle {
                anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                width: parent.width * Math.max(0, Math.min(1, root.lapProgress / 100))
                color: Qt.rgba(Theme.Tokens.racingPurple.r, Theme.Tokens.racingPurple.g, Theme.Tokens.racingPurple.b, 0.35)
                Behavior on width { NumberAnimation { duration: 50; easing.type: Easing.Linear } }
            }

            // Sector dividers
            Repeater {
                model: [33.3, 66.6]
                Rectangle {
                    required property var modelData
                    x: progressTrack.width * modelData / 100
                    width: 1; height: parent.height
                    color: Theme.Tokens.racingPurple
                    opacity: 0.25
                }
            }

            // Playhead dot
            Rectangle {
                width: 5; height: 5; radius: 2.5
                color: Theme.Tokens.racingPurple
                opacity: 0.7
                x: progressTrack.width * Math.max(0, Math.min(1, root.lapProgress / 100)) - 2.5
                y: (parent.height - height) / 2
                Behavior on x { NumberAnimation { duration: 50; easing.type: Easing.Linear } }
            }
        }
    }
}
