pragma Singleton

import QtQuick

QtObject {
    readonly property color windowBg: "#090b0d"
    readonly property color chromeBg: "#0e1115"
    readonly property color paneBg: "#11151a"
    readonly property color paneAltBg: "#161b21"
    readonly property color paneRaised: "#1b2128"
    readonly property color border: "#27303a"
    readonly property color borderStrong: "#394452"
    readonly property color text: "#eef2f6"
    readonly property color textMuted: "#9aa4b2"
    readonly property color textDim: "#69727f"
    readonly property color accent: "#c62828"
    readonly property color accentSoft: "#6a1b1b"
    readonly property color success: "#21c26d"
    readonly property color warning: "#d4a64f"
    readonly property color error: "#ef4444"
    readonly property color selection: "#18202a"
    readonly property color selectionBorder: "#c62828"
    readonly property color canvasBg: "#06080a"
    readonly property color canvasFrame: "#1a2027"

    readonly property int radiusXs: 4
    readonly property int radiusSm: 6
    readonly property int radiusMd: 8
    readonly property int radiusLg: 12

    readonly property int space2: 4
    readonly property int space3: 6
    readonly property int space4: 8
    readonly property int space5: 12
    readonly property int space6: 16
    readonly property int space7: 20
    readonly property int space8: 24

    readonly property int toolbarHeight: 44
    readonly property int controlHeight: 30
    readonly property int navWidth: 92
    readonly property int sidebarWidth: 320
    readonly property int inspectorWidth: 360
    readonly property int statusHeight: 28
    readonly property int dockHeight: 42

    readonly property int fontScreen: 18
    readonly property int fontSection: 14
    readonly property int fontBody: 12
    readonly property int fontMeta: 11
    readonly property int fontMicro: 10
}
