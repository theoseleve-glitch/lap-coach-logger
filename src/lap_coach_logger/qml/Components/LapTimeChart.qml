import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme

Item {
    id: root

    property var laps: []

    implicitHeight: 140

    // Compute time range for relative bar scaling
    readonly property real minTime: {
        if (!laps || laps.length === 0) return 0
        var m = laps[0].time_s
        for (var i = 1; i < laps.length; i++)
            if (laps[i].time_s < m) m = laps[i].time_s
        return m
    }
    readonly property real maxTime: {
        if (!laps || laps.length === 0) return 0
        var m = laps[0].time_s
        for (var i = 1; i < laps.length; i++)
            if (laps[i].time_s > m) m = laps[i].time_s
        return m
    }

    // Margin around the range for visual headroom
    readonly property real rangeMargin: {
        var span = maxTime - minTime
        return span > 0 ? span * 0.15 : 1.0
    }
    readonly property real scaleMin: minTime - rangeMargin
    readonly property real scaleMax: maxTime + rangeMargin

    // Available height for bars (excluding labels above/below)
    readonly property real barAreaHeight: root.height - 36  // ~18px top labels + ~18px bottom labels

    RowLayout {
        anchors.fill: parent
        spacing: 2

        Repeater {
            model: root.laps

            Item {
                id: barDelegate

                required property var modelData
                required property int index

                readonly property bool isBest: modelData.is_best === true
                readonly property bool isTrackLimits: modelData.status === "track_limits"
                readonly property real timeS: modelData.time_s

                // Map time to a 40%-100% height range
                readonly property real normalised: {
                    var range = root.scaleMax - root.scaleMin
                    if (range <= 0) return 0.7
                    return 0.4 + 0.6 * ((timeS - root.scaleMin) / range)
                }

                Layout.fillWidth: true
                Layout.fillHeight: true

                // Time label above bar
                Text {
                    id: timeLabel
                    anchors {
                        bottom: bar.top
                        bottomMargin: 2
                        horizontalCenter: parent.horizontalCenter
                    }
                    text: formatTime(barDelegate.timeS)
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    color: barDelegate.isBest ? Theme.Tokens.pitOrange
                         : barDelegate.isTrackLimits ? Theme.Tokens.marshalYellow
                         : "#646464"
                    horizontalAlignment: Text.AlignHCenter
                }

                // Bar
                Rectangle {
                    id: bar
                    anchors {
                        bottom: lapLabel.top
                        bottomMargin: 2
                        horizontalCenter: parent.horizontalCenter
                    }
                    width: Math.max(parent.width - 4, 4)
                    height: Math.max(root.barAreaHeight * barDelegate.normalised, 4)
                    radius: 2

                    color: barDelegate.isBest
                           ? Qt.rgba(Theme.Tokens.pitOrange.r,
                                     Theme.Tokens.pitOrange.g,
                                     Theme.Tokens.pitOrange.b, 0.30)
                         : barDelegate.isTrackLimits
                           ? Qt.rgba(Theme.Tokens.marshalYellow.r,
                                     Theme.Tokens.marshalYellow.g,
                                     Theme.Tokens.marshalYellow.b, 0.20)
                         : Qt.rgba(Theme.Tokens.chalk.r,
                                   Theme.Tokens.chalk.g,
                                   Theme.Tokens.chalk.b, 0.15)

                    border.width: barDelegate.isBest || barDelegate.isTrackLimits ? 1 : 0
                    border.color: barDelegate.isBest
                                  ? Qt.rgba(Theme.Tokens.pitOrange.r,
                                            Theme.Tokens.pitOrange.g,
                                            Theme.Tokens.pitOrange.b, 0.50)
                                : barDelegate.isTrackLimits
                                  ? Qt.rgba(Theme.Tokens.marshalYellow.r,
                                            Theme.Tokens.marshalYellow.g,
                                            Theme.Tokens.marshalYellow.b, 0.30)
                                : "transparent"
                }

                // Lap label below bar
                Text {
                    id: lapLabel
                    anchors {
                        bottom: parent.bottom
                        horizontalCenter: parent.horizontalCenter
                    }
                    text: barDelegate.isBest
                          ? ("L" + modelData.lap + " \u2605")
                          : ("L" + modelData.lap)
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 9
                    font.weight: barDelegate.isBest ? Font.Bold : Font.Normal
                    color: barDelegate.isBest ? Theme.Tokens.pitOrange : "#646464"
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }

    // Format seconds to M:SS.sss
    function formatTime(secs) {
        if (secs <= 0) return "--"
        var mins = Math.floor(secs / 60)
        var s = secs - mins * 60
        var secStr = s.toFixed(3)
        if (s < 10) secStr = "0" + secStr
        return mins + ":" + secStr
    }
}
