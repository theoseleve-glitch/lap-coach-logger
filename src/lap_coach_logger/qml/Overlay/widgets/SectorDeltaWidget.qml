import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  SectorDeltaWidget — per-sector delta to best lap (300 x 60).

    Three cells side by side: S1, S2, S3. Each cell shows the signed
    delta for that sector ("-0.2" green, "+0.3" red). Resets each lap.

    Degraded rendering: cells with missing data show "—" in steel.   */
Rectangle {
    id: root

    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 300
    height: 60
    color: "transparent"

    // -- public API -------------------------------------------------------
    // Array of deltas [s1, s2, s3] in seconds. Empty = no data.
    property var deltas: []
    // T164: degraded state — telemetry stalled. When true
    // every sector flips to "—" simultaneously (re-uses the
    // existing null path), so the user can tell the whole
    // pipeline died from individual missing-sector data.
    property bool degraded: false

    // -- helpers ----------------------------------------------------------
    function deltaFor(idx) {
        if (root.degraded) return null
        if (!deltas || deltas.length <= idx) return null
        var v = deltas[idx]
        return isFinite(v) ? v : null
    }

    function colorFor(d) {
        if (d === null || Math.abs(d) < 0.02) return Theme.Tokens.chalk
        return d < 0 ? Theme.Tokens.acidGreen : Theme.Tokens.safetyRed
    }

    function formatDelta(d) {
        if (d === null) return "\u2014"
        var sign = d > 0 ? "+" : ""
        return sign + d.toFixed(2)
    }

    // Background
    Rectangle {
        anchors.fill: parent
        radius: 8
        color: Qt.rgba(0, 0, 0, 0.78)
        border.width: 1
        border.color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g,
                              Theme.Tokens.chalk.b, 0.06)
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 1

        // Inline sector cell component
        component SectorCell: Item {
            property int sector: 1
            property var value: null

            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                anchors.centerIn: parent
                spacing: 0

                Text {
                    text: "S" + parent.parent.sector
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(8 * root.fontScale)
                    font.weight: Font.Bold
                    font.letterSpacing: 1.0
                    color: Theme.Tokens.steel
                    opacity: 0.7
                    Layout.alignment: Qt.AlignHCenter
                }
                Text {
                    text: root.formatDelta(parent.parent.value)
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(18 * root.fontScale)
                    font.weight: Font.Bold
                    color: root.colorFor(parent.parent.value)
                    opacity: parent.parent.value === null ? 0.4 : 1.0
                    Layout.alignment: Qt.AlignHCenter
                    Behavior on color { ColorAnimation { duration: 180 } }
                }
            }
        }

        SectorCell { sector: 1; value: root.deltaFor(0) }
        Rectangle {
            width: 1; Layout.fillHeight: true; Layout.topMargin: 8; Layout.bottomMargin: 8
            color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08)
        }
        SectorCell { sector: 2; value: root.deltaFor(1) }
        Rectangle {
            width: 1; Layout.fillHeight: true; Layout.topMargin: 8; Layout.bottomMargin: 8
            color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08)
        }
        SectorCell { sector: 3; value: root.deltaFor(2) }
    }
}
