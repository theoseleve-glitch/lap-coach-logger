pragma Singleton
import QtQuick

QtObject {
    // Page transitions
    readonly property int pageOutDuration: 200
    readonly property int pageInDuration: 250
    readonly property int pageSlideOffset: 30
    readonly property int pageOverlap: 40
    readonly property int pageCurve: Easing.OutCubic

    // Push navigation (History -> Review)
    readonly property int pushDuration: 300
    readonly property int pushCurve: Easing.OutQuint
    readonly property int popCurve: Easing.InQuad

    // Micro-interactions
    readonly property int hoverDuration: 120
    readonly property int pressDuration: 80
    readonly property real hoverScale: 1.02
    readonly property real pressScale: 0.98
    readonly property int focusDuration: 150

    // Status changes
    readonly property int statusColorDuration: 400
    readonly property int recordingPulseDuration: 1500
    readonly property int metricCountUpDuration: 300

    // Slide-overs
    readonly property int slideOverOpenDuration: 300
    readonly property int slideOverCloseDuration: 200
    readonly property int dimDuration: 250
    readonly property real dimOpacity: 0.4

    // Dialogs
    readonly property int dialogDuration: 200
    readonly property real dialogStartScale: 0.95
}
