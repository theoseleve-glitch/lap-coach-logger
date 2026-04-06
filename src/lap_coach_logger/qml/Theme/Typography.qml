pragma Singleton
import QtQuick

QtObject {
    readonly property string displayFamily: "Segoe UI"
    readonly property string bodyFamily: "Segoe UI"
    readonly property string monoFamily: "Consolas"
    readonly property int displaySize: 32
    readonly property int displayWeight: Font.Bold
    readonly property int titleSize: 22
    readonly property int titleWeight: Font.Bold
    readonly property int headingSize: 17
    readonly property int headingWeight: Font.DemiBold
    readonly property int bodySize: 14
    readonly property int bodyWeight: Font.Normal
    readonly property int captionSize: 12
    readonly property int captionWeight: Font.Normal
    readonly property int dataSize: 28
    readonly property int dataWeight: Font.Bold
    readonly property int microSize: 10
    readonly property int microWeight: Font.Bold
    readonly property real microSpacing: 1.5
}
