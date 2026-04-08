import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  DataBlocksWidget — compact 3-column data blocks grid (320x200).
    Each block: centered label + value, color-coded per block,
    with subtle borders between cells.                              */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 320
    height: 200
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property var blocks: [
        { label: "SPEED",    value: "---", color: "" },
        { label: "GEAR",     value: "-",   color: "" },
        { label: "RPM",      value: "---", color: "" },
        { label: "THROTTLE", value: "---", color: "" },
        { label: "BRAKE",    value: "---", color: "" },
        { label: "DELTA",    value: "---", color: "" }
    ]

    // ── null-safe derived ───────────────────────────────────────────
    readonly property var safeBlocks: Array.isArray(blocks) ? blocks : []
    readonly property int blockCount: safeBlocks.length

    // ── inline component ────────────────────────────────────────────
    component DataBlock: Rectangle {
        id: block
        required property int index

        readonly property var entry: {
            var list = root.safeBlocks
            return (index >= 0 && index < list.length) ? list[index] : null
        }
        readonly property string blockLabel:
            (entry && typeof entry.label === "string") ? entry.label : ""
        readonly property string blockValue:
            (entry && entry.value !== undefined && entry.value !== null)
            ? String(entry.value) : "---"
        readonly property color blockColor:
            (entry && entry.color) ? entry.color : Theme.Tokens.chalk

        Layout.fillWidth: true
        Layout.preferredHeight: 52
        radius: Theme.Tokens.radiusSm
        color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.04)
        border.width: 1
        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.06)

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 2

            Text {
                text: block.blockLabel
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(7 * root.fontScale)
                font.weight: Font.Bold
                font.letterSpacing: 0.8
                color: Theme.Tokens.steel
                Layout.alignment: Qt.AlignHCenter
            }

            Text {
                text: block.blockValue
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.headingSize
                font.weight: Font.Bold
                color: block.blockColor
                Layout.alignment: Qt.AlignHCenter
            }
        }
    }

    // ── layout ──────────────────────────────────────────────────────
    ColumnLayout {
        anchors {
            fill: parent
            topMargin: Theme.Tokens.md
            bottomMargin: Theme.Tokens.md
            leftMargin: Theme.Tokens.md
            rightMargin: Theme.Tokens.md
        }
        spacing: 0

        // ── Header ─────────────────────────────────────────────────
        Text {
            text: "DATA BLOCKS"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.microSize
            font.weight: Theme.Typography.microWeight
            font.letterSpacing: Theme.Typography.microSpacing
            color: Theme.Tokens.steel
        }

        // ── Separator ──────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.Tokens.sm
            Rectangle {
                anchors.centerIn: parent
                width: parent.width; height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5;
                        color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // ── Empty state ────────────────────────────────────────────
        Text {
            visible: root.blockCount === 0
            text: "No data"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.captionSize
            color: Theme.Tokens.steel
            opacity: 0.4
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: Theme.Tokens.xl
        }

        // ── Blocks grid (3 columns) ───────────────────────────────
        GridLayout {
            visible: root.blockCount > 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 3
            rowSpacing: Theme.Tokens.sm
            columnSpacing: Theme.Tokens.sm

            Repeater {
                model: root.blockCount
                delegate: DataBlock {}
            }
        }
    }
}
