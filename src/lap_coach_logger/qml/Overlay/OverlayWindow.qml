import QtQuick
import "../Theme" as Theme
import "widgets" as Widgets

// Pre-declared overlay windows. Visibility polled via _tick timer.
// x/y set once via Component.onCompleted, NOT bound (so drag works).

Item {
    id: root

    property int _tick: 0
    Timer {
        interval: 500; running: true; repeat: true
        onTriggered: root._tick++
    }

    function isOn(wid) {
        void(_tick)
        return overlayVM && overlayVM.isWidgetEnabled(wid) && overlayVM.shouldShowOverlays
    }
    function gw(wid, key, def) {
        if (!overlayVM) return def
        if (key === "width") return overlayVM.getWidgetWidth(wid)
        if (key === "height") return overlayVM.getWidgetHeight(wid)
        if (key === "opacity") return overlayVM.getWidgetOpacity(wid)
        if (key === "fontScale") return overlayVM.getWidgetFontScale(wid)
        if (key === "borderRadius") return overlayVM.getWidgetBorderRadius(wid)
        return def
    }

    // Macro-like helper: set initial position once, then never re-bind
    component OW: OverlayWidget {
        property string _wid: ""
        Component.onCompleted: {
            if (overlayVM && _wid) {
                x = overlayVM.getWidgetX(_wid)
                y = overlayVM.getWidgetY(_wid)
            }
        }
    }

    OW {
        _wid: "delta_timing"; widgetId: "delta_timing"
        visible: root.isOn("delta_timing")
        width: root.gw("delta_timing","width",320); height: root.gw("delta_timing","height",200)
        opacity: root.gw("delta_timing","opacity",0.92)
        fontScale: root.gw("delta_timing","fontScale",1.0)
        borderRadius: root.gw("delta_timing","borderRadius",12)
        Widgets.DeltaTimeWidget {
            anchors.fill: parent; anchors.margins: 4
            delta: overlayVM ? overlayVM.liveDelta : 0
            lapTime: overlayVM ? overlayVM.currentLapTime || "0:00.000" : "0:00.000"
            bestTime: overlayVM ? overlayVM.bestTime || "\u2014" : "\u2014"
            lapNumber: overlayVM ? overlayVM.lapNumber : 0
            totalLaps: 0; lapProgress: overlayVM ? overlayVM.lapProgress : 0
            sectors: overlayVM ? overlayVM.sectorStates || [] : []
        }
    }

    OW {
        _wid: "inputs_grip"; widgetId: "inputs_grip"
        visible: root.isOn("inputs_grip")
        width: root.gw("inputs_grip","width",240); height: root.gw("inputs_grip","height",260)
        opacity: root.gw("inputs_grip","opacity",0.92)
        fontScale: root.gw("inputs_grip","fontScale",1.0)
        borderRadius: root.gw("inputs_grip","borderRadius",12)
        Widgets.InputsWidget {
            anchors.fill: parent; anchors.margins: 4
            throttle: overlayVM ? overlayVM.throttlePct : 0
            brake: overlayVM ? overlayVM.brakePct : 0
            steering: overlayVM ? overlayVM.steeringDeg / 450.0 : 0
            gForceX: overlayVM ? overlayVM.latAccelG : 0
            gForceY: overlayVM ? overlayVM.longAccelG : 0
            lockup: overlayVM ? overlayVM.lockupActive : false
            wheelspin: overlayVM ? overlayVM.wheelspinActive : false
            smoothness: overlayVM ? overlayVM.inputSmoothness : 0.75
        }
    }

    OW {
        _wid: "fuel_strategy"; widgetId: "fuel_strategy"
        visible: root.isOn("fuel_strategy")
        width: root.gw("fuel_strategy","width",180); height: root.gw("fuel_strategy","height",240)
        opacity: root.gw("fuel_strategy","opacity",0.92)
        fontScale: root.gw("fuel_strategy","fontScale",1.0)
        borderRadius: root.gw("fuel_strategy","borderRadius",12)
        Widgets.FuelWidget {
            anchors.fill: parent; anchors.margins: 4
            remaining: overlayVM ? overlayVM.fuelLevel : 0
            lapsLeft: overlayVM ? overlayVM.fuelLapsLeft : 0
            fuelPerLap: overlayVM ? overlayVM.fuelPerLap : 0
            state: overlayVM ? overlayVM.fuelState || "SAFE" : "SAFE"
            pitWindow: ""; totalLaps: 0
            currentLap: overlayVM ? overlayVM.lapNumber : 0
        }
    }

    OW {
        _wid: "lap_timing"; widgetId: "lap_timing"
        visible: root.isOn("lap_timing")
        width: root.gw("lap_timing","width",280); height: root.gw("lap_timing","height",120)
        opacity: root.gw("lap_timing","opacity",0.92)
        fontScale: root.gw("lap_timing","fontScale",1.0)
        borderRadius: root.gw("lap_timing","borderRadius",12)
        Widgets.LapTimingWidget {
            anchors.fill: parent; anchors.margins: 4
            currentTime: overlayVM ? overlayVM.currentLapTime || "0:00.000" : "0:00.000"
            lastTime: overlayVM ? overlayVM.lastTime || "\u2014" : "\u2014"
            bestTime: overlayVM ? overlayVM.bestTime || "\u2014" : "\u2014"
            gap: ""
        }
    }

    OW {
        _wid: "delta_bar"; widgetId: "delta_bar"
        visible: root.isOn("delta_bar")
        width: root.gw("delta_bar","width",300); height: root.gw("delta_bar","height",60)
        opacity: root.gw("delta_bar","opacity",0.92)
        fontScale: root.gw("delta_bar","fontScale",1.0)
        borderRadius: root.gw("delta_bar","borderRadius",12)
        Widgets.DeltaBarWidget {
            anchors.fill: parent; anchors.margins: 4
            delta: overlayVM ? overlayVM.liveDelta : 0
        }
    }

    OW {
        _wid: "session_timer"; widgetId: "session_timer"
        visible: root.isOn("session_timer")
        width: root.gw("session_timer","width",200); height: root.gw("session_timer","height",80)
        opacity: root.gw("session_timer","opacity",0.92)
        fontScale: root.gw("session_timer","fontScale",1.0)
        borderRadius: root.gw("session_timer","borderRadius",12)
        Widgets.SessionTimerWidget {
            anchors.fill: parent; anchors.margins: 4
            elapsed: overlayVM ? overlayVM.elapsed || "0:00" : "0:00"
            sessionType: overlayVM ? overlayVM.sessionType || "Practice" : "Practice"
            timeRemaining: ""
        }
    }

    OW {
        _wid: "flags"; widgetId: "flags"
        visible: root.isOn("flags")
        width: root.gw("flags","width",160); height: root.gw("flags","height",100)
        opacity: root.gw("flags","opacity",0.92)
        fontScale: root.gw("flags","fontScale",1.0)
        borderRadius: root.gw("flags","borderRadius",12)
        Widgets.FlagsWidget {
            anchors.fill: parent; anchors.margins: 4
            flag: overlayVM ? overlayVM.currentFlag || "green" : "green"
        }
    }

    OW {
        _wid: "radar"; widgetId: "radar"
        visible: root.isOn("radar")
        width: root.gw("radar","width",200); height: root.gw("radar","height",200)
        opacity: root.gw("radar","opacity",0.92)
        fontScale: root.gw("radar","fontScale",1.0)
        borderRadius: root.gw("radar","borderRadius",12)
        Widgets.RadarWidget { anchors.fill: parent; anchors.margins: 4 }
    }

    OW {
        _wid: "weather_monitor"; widgetId: "weather_monitor"
        visible: root.isOn("weather_monitor")
        width: root.gw("weather_monitor","width",200); height: root.gw("weather_monitor","height",160)
        opacity: root.gw("weather_monitor","opacity",0.92)
        fontScale: root.gw("weather_monitor","fontScale",1.0)
        borderRadius: root.gw("weather_monitor","borderRadius",12)
        Widgets.WeatherMonitorWidget {
            anchors.fill: parent; anchors.margins: 4
            trackTemp: overlayVM ? overlayVM.trackTemp : 0
            airTemp: overlayVM ? overlayVM.airTemp : 0
        }
    }

    OW {
        _wid: "gforce_meter_full"; widgetId: "gforce_meter_full"
        visible: root.isOn("gforce_meter_full")
        width: root.gw("gforce_meter_full","width",200); height: root.gw("gforce_meter_full","height",200)
        opacity: root.gw("gforce_meter_full","opacity",0.92)
        fontScale: root.gw("gforce_meter_full","fontScale",1.0)
        borderRadius: root.gw("gforce_meter_full","borderRadius",12)
        Widgets.GForceMeterWidget {
            anchors.fill: parent; anchors.margins: 4
            latG: overlayVM ? overlayVM.latAccelG : 0
            longG: overlayVM ? overlayVM.longAccelG : 0
        }
    }

    OW {
        _wid: "input_telemetry"; widgetId: "input_telemetry"
        visible: root.isOn("input_telemetry")
        width: root.gw("input_telemetry","width",280); height: root.gw("input_telemetry","height",180)
        opacity: root.gw("input_telemetry","opacity",0.92)
        fontScale: root.gw("input_telemetry","fontScale",1.0)
        borderRadius: root.gw("input_telemetry","borderRadius",12)
        Widgets.InputTelemetryWidget {
            anchors.fill: parent; anchors.margins: 4
            throttle: overlayVM ? overlayVM.throttlePct : 0
            brake: overlayVM ? overlayVM.brakePct : 0
            clutch: overlayVM ? overlayVM.clutchPct : 0
            steering: overlayVM ? overlayVM.steeringDeg / 450.0 : 0
            gear: overlayVM ? overlayVM.gear : 0
            rpm: overlayVM ? overlayVM.rpm : 0
            maxRpm: 8500
        }
    }

    OW {
        _wid: "fuel_calculator"; widgetId: "fuel_calculator"
        visible: root.isOn("fuel_calculator")
        width: root.gw("fuel_calculator","width",220); height: root.gw("fuel_calculator","height",200)
        opacity: root.gw("fuel_calculator","opacity",0.92)
        fontScale: root.gw("fuel_calculator","fontScale",1.0)
        borderRadius: root.gw("fuel_calculator","borderRadius",12)
        Widgets.FuelCalculatorWidget {
            anchors.fill: parent; anchors.margins: 4
            fuelLevel: overlayVM ? overlayVM.fuelLevel : 0
            fuelPerLap: overlayVM ? overlayVM.fuelPerLap : 0
            lapsLeft: overlayVM ? overlayVM.fuelLapsLeft : 0
        }
    }
}
