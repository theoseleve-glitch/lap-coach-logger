pragma Singleton
import QtQuick

QtObject {
    // Surface elevation (4-tier near-black scale — pure #000 is retired)
    readonly property color void_: "#050607"
    readonly property color surface: "#0A0B0E"
    readonly property color elevated: "#141519"
    readonly property color raised: "#1E1F25"

    // Accent palette
    readonly property color chalk: "#F0EDE5"
    readonly property color steel: "#949494"
    readonly property color pitOrange: "#C9A84C"
    readonly property color acidGreen: "#22C55E"
    readonly property color safetyRed: "#FF2A2A"
    readonly property color marshalYellow: "#FACC15"
    readonly property color racingPurple: "#8B5CF6"

    // Spacing (8px base grid)
    readonly property int xs: 4
    readonly property int sm: 8
    readonly property int md: 12
    readonly property int lg: 16
    readonly property int xl: 24
    readonly property int xxl: 32
    readonly property int xxxl: 48
    readonly property int xxxxl: 64

    // Border radius
    readonly property int radiusSm: 6
    readonly property int radiusMd: 10
    readonly property int radiusLg: 14
    readonly property int radiusXl: 20

    // Opacity helpers
    function subtle(c, a) { return Qt.rgba(c.r, c.g, c.b, a === undefined ? 0.06 : a) }
    function medium(c, a) { return Qt.rgba(c.r, c.g, c.b, a === undefined ? 0.10 : a) }
}
