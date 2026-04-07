import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  LapTimingWidget — compact lap timing overlay (280 x 120).
    Displays current lap time (hero, large mono), last lap, best lap
    (pitOrange), delta vs best (green/red coloring), gap to leader,
    and a personal best indicator flash.                              */
GlassSurface {
    id: root
    width: 280
    implicitHeight: col.implicitHeight + 20

    // ── public API ──────────────────────────────────────────────────
    property string currentTime: ""
    property string lastTime: ""
    property string bestTime: ""
    property string deltaVsBest: ""     // e.g. "+0.312" or "-0.456"
    property string gap: ""
    property bool   isPersonalBest: false

    // ── derived ─────────────────────────────────────────────────────
    readonly property string safeCurrentTime: (root.currentTime && root.currentTime.length > 0)
                                               ? root.currentTime : "-:---.---"
    readonly property string safeLastTime:    (root.lastTime && root.lastTime.length > 0)
                                               ? root.lastTime : "-:---.---"
    readonly property string safeBestTime:    (root.bestTime && root.bestTime.length > 0)
                                               ? root.bestTime : "-:---.---"
    readonly property string safeDelta:       (root.deltaVsBest && root.deltaVsBest.length > 0)
                                               ? root.deltaVsBest : ""
    readonly property string safeGap:         (root.gap && root.gap.length > 0)
                                               ? root.gap : ""

    // Delta color: starts with "-" = faster = green, "+" = slower = red
    readonly property color deltaColor: {
        if (!root.safeDelta || root.safeDelta.length === 0)
            return Theme.Tokens.steel
        if (root.safeDelta.charAt(0) === "-")
            return Theme.Tokens.acidGreen
        return Theme.Tokens.safetyRed
    }

    // ── Inline component: gradient separator ────────────────────────
    component GradientDivider: Item {
        Layout.fillWidth: true
        Layout.preferredHeight: 7
        Rectangle {
            anchors.centerIn: parent
            width: parent.width
            height: 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }
    }

    // ── Inline component: micro label ───────────────────────────────
    component MicroLabel: Text {
        font.family: Theme.Typography.monoFamily
        font.pixelSize: 9
        font.weight: Font.Bold
        font.letterSpacing: 1.2
        color: Theme.Tokens.steel
    }

    // ── Personal best flash overlay ─────────────────────────────────
    Rectangle {
        id: pbFlash
        anchors.fill: parent
        radius: root.radius
        color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.0)
        z: 10

        SequentialAnimation {
            id: pbFlashAnim
            NumberAnimation {
                target: pbFlash; property: "color"
                to: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.18)
                duration: 150
            }
            NumberAnimation {
                target: pbFlash; property: "color"
                to: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.0)
                duration: 600; easing.type: Easing.OutCubic
            }
        }
    }

    onIsPersonalBestChanged: {
        if (root.isPersonalBest) pbFlashAnim.start()
    }

    ColumnLayout {
        id: col
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 14
            rightMargin: 14
        }
        spacing: 0

        // ── Row 1: Current lap time (hero element) ─────────────────
        ColumnLayout {
            spacing: 1

            MicroLabel { text: "CURRENT" }

            Text {
                text: root.safeCurrentTime
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 32
                font.weight: Font.Bold
                color: Theme.Tokens.chalk
                Layout.fillWidth: true
            }
        }

        GradientDivider {}

        // ── Row 2: Last + Best + Delta ─────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            // Last lap
            ColumnLayout {
                spacing: 1

                MicroLabel { text: "LAST" }

                Text {
                    text: root.safeLastTime
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 13
                    font.weight: Font.Bold
                    color: Theme.Tokens.chalk
                }
            }

            Item { Layout.fillWidth: true }

            // Delta vs best
            ColumnLayout {
                spacing: 1
                visible: root.safeDelta.length > 0
                Layout.alignment: Qt.AlignRight

                MicroLabel {
                    text: "DELTA"
                    horizontalAlignment: Text.AlignRight
                    Layout.fillWidth: true
                }

                Text {
                    text: root.safeDelta
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 13
                    font.weight: Font.Bold
                    color: root.deltaColor
                    horizontalAlignment: Text.AlignRight
                    Layout.fillWidth: true

                    Behavior on color { ColorAnimation { duration: 200 } }
                }
            }

            // Spacer between delta and best if both shown
            Item {
                visible: root.safeDelta.length > 0
                Layout.preferredWidth: 12
            }

            // Best lap (pitOrange)
            ColumnLayout {
                spacing: 1
                Layout.alignment: Qt.AlignRight

                MicroLabel {
                    text: "BEST"
                    horizontalAlignment: Text.AlignRight
                    Layout.fillWidth: true
                }

                Text {
                    text: root.safeBestTime
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 13
                    font.weight: Font.Bold
                    color: Theme.Tokens.pitOrange
                    horizontalAlignment: Text.AlignRight
                    Layout.fillWidth: true
                }
            }
        }

        // ── Row 3: Gap to leader ───────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4
            visible: root.safeGap.length > 0

            MicroLabel { text: "GAP" }

            Item { Layout.fillWidth: true }

            Text {
                text: root.safeGap
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 13
                font.weight: Font.Bold
                color: Theme.Tokens.marshalYellow
            }
        }
    }
}
