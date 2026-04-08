import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  AdvancedPanelWidget — multi-row configurable telemetry panel (360x280).
    Two-column grid of ChannelRow components with color-coded values
    and dimmer unit labels.  Header reads "TELEMETRY".                  */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 360
    height: 280
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    property var channels: [
        { label: "SPEED",      value: "---",  unit: "km/h", color: "" },
        { label: "RPM",        value: "---",  unit: "",     color: "" },
        { label: "GEAR",       value: "-",    unit: "",     color: "" },
        { label: "BRK TEMP",   value: "---",  unit: "C",    color: "" },
        { label: "TYRE TEMP",  value: "---",  unit: "C",    color: "" },
        { label: "FUEL",       value: "---",  unit: "L",    color: "" },
        { label: "POSITION",   value: "-",    unit: "",     color: "" },
        { label: "GAP",        value: "---",  unit: "s",    color: "" }
    ]

    // ── null-safe derived ───────────────────────────────────────────
    readonly property var safeChannels: Array.isArray(channels) ? channels : []
    readonly property int channelCount: safeChannels.length

    // ── inline component ────────────────────────────────────────────
    component ChannelRow: Rectangle {
        id: chRow
        required property int index

        readonly property var ch: {
            var list = root.safeChannels
            return (index >= 0 && index < list.length) ? list[index] : null
        }
        readonly property string chLabel:
            (ch && typeof ch.label === "string") ? ch.label : ""
        readonly property string chValue:
            (ch && ch.value !== undefined && ch.value !== null)
            ? String(ch.value) : "---"
        readonly property string chUnit:
            (ch && typeof ch.unit === "string") ? ch.unit : ""
        readonly property color chColor:
            (ch && ch.color) ? ch.color : Theme.Tokens.chalk

        Layout.fillWidth: true
        Layout.preferredHeight: 28
        radius: Theme.Tokens.xs
        color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.03)

        RowLayout {
            anchors {
                fill: parent
                leftMargin: Theme.Tokens.sm
                rightMargin: Theme.Tokens.sm
            }
            spacing: Theme.Tokens.xs

            Text {
                text: chRow.chLabel
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(8 * root.fontScale)
                font.weight: Font.Bold
                font.letterSpacing: 0.8
                color: Theme.Tokens.steel
                Layout.preferredWidth: 60
            }

            Item { Layout.fillWidth: true }

            // Value
            Text {
                text: chRow.chValue
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.captionSize
                font.weight: Font.Bold
                color: chRow.chColor
                horizontalAlignment: Text.AlignRight
            }

            // Unit (smaller, dimmer)
            Text {
                visible: chRow.chUnit !== ""
                text: chRow.chUnit
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(8 * root.fontScale)
                font.weight: Font.Normal
                color: Theme.Tokens.steel
                opacity: 0.5
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
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.Tokens.sm

            Text {
                text: "TELEMETRY"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Theme.Typography.microWeight
                font.letterSpacing: Theme.Typography.microSpacing
                color: Theme.Tokens.steel
            }

            Rectangle {
                implicitWidth: countLabel.implicitWidth + Theme.Tokens.sm
                implicitHeight: 14
                radius: Theme.Tokens.radiusSm / 2
                color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.12)

                Text {
                    id: countLabel
                    anchors.centerIn: parent
                    text: root.channelCount + " CH"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(7 * root.fontScale)
                    font.weight: Font.Bold
                    color: Theme.Tokens.pitOrange
                }
            }

            Item { Layout.fillWidth: true }
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
            visible: root.channelCount === 0
            text: "No channels"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.captionSize
            color: Theme.Tokens.steel
            opacity: 0.4
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: Theme.Tokens.xl
        }

        // ── Channel grid (2 columns) ──────────────────────────────
        GridLayout {
            visible: root.channelCount > 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 2
            rowSpacing: Theme.Tokens.xs
            columnSpacing: Theme.Tokens.md

            Repeater {
                model: root.channelCount
                delegate: ChannelRow {}
            }
        }
    }
}
