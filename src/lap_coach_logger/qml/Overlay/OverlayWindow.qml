import QtQuick
import "../Theme" as Theme
import "widgets" as Widgets

// Pre-declared overlay windows. Each widget has its own OverlayWidget
// instance with visibility bound directly to the VM. No dynamic creation.

Item {
    id: root

    // Helper: read settings via Slots (reactive through _syncTimer)
    property int _tick: 0
    Timer {
        id: _syncTimer
        interval: 500
        running: true
        repeat: true
        onTriggered: root._tick++
    }

    function ws(wid, key, def) {
        void(_tick)
        if (!overlayVM) return def
        if (key === "enabled") return overlayVM.isWidgetEnabled(wid)
        if (key === "width") return overlayVM.getWidgetWidth(wid)
        if (key === "height") return overlayVM.getWidgetHeight(wid)
        if (key === "opacity") return overlayVM.getWidgetOpacity(wid)
        if (key === "x") return overlayVM.getWidgetX(wid)
        if (key === "y") return overlayVM.getWidgetY(wid)
        if (key === "fontScale") return overlayVM.getWidgetFontScale(wid)
        if (key === "borderRadius") return overlayVM.getWidgetBorderRadius(wid)
        return def
    }

    function shouldShow(wid) {
        void(_tick)
        return overlayVM && overlayVM.isWidgetEnabled(wid) && overlayVM.shouldShowOverlays
    }

    // ═══════════════════════════════════════════════════════════════
    // Pre-declared overlay widget windows
    // ═══════════════════════════════════════════════════════════════

    OverlayWidget {
        visible: root.shouldShow("delta_timing")
        widgetId: "delta_timing"
        width: root.ws("delta_timing", "width", 320)
        height: root.ws("delta_timing", "height", 200)
        opacity: root.ws("delta_timing", "opacity", 0.92)
        x: root.ws("delta_timing", "x", 100); y: root.ws("delta_timing", "y", 80)
        fontScale: root.ws("delta_timing", "fontScale", 1.0)
        borderRadius: root.ws("delta_timing", "borderRadius", 12)
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

    OverlayWidget {
        visible: root.shouldShow("inputs_grip")
        widgetId: "inputs_grip"
        width: root.ws("inputs_grip", "width", 240)
        height: root.ws("inputs_grip", "height", 260)
        opacity: root.ws("inputs_grip", "opacity", 0.92)
        x: root.ws("inputs_grip", "x", 440); y: root.ws("inputs_grip", "y", 80)
        fontScale: root.ws("inputs_grip", "fontScale", 1.0)
        borderRadius: root.ws("inputs_grip", "borderRadius", 12)
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

    OverlayWidget {
        visible: root.shouldShow("fuel_strategy")
        widgetId: "fuel_strategy"
        width: root.ws("fuel_strategy", "width", 180)
        height: root.ws("fuel_strategy", "height", 240)
        opacity: root.ws("fuel_strategy", "opacity", 0.92)
        x: root.ws("fuel_strategy", "x", 700); y: root.ws("fuel_strategy", "y", 80)
        fontScale: root.ws("fuel_strategy", "fontScale", 1.0)
        borderRadius: root.ws("fuel_strategy", "borderRadius", 12)
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

    OverlayWidget {
        visible: root.shouldShow("lap_timing")
        widgetId: "lap_timing"
        width: root.ws("lap_timing", "width", 280)
        height: root.ws("lap_timing", "height", 120)
        opacity: root.ws("lap_timing", "opacity", 0.92)
        x: root.ws("lap_timing", "x", 100); y: root.ws("lap_timing", "y", 300)
        fontScale: root.ws("lap_timing", "fontScale", 1.0)
        borderRadius: root.ws("lap_timing", "borderRadius", 12)
        Widgets.LapTimingWidget {
            anchors.fill: parent; anchors.margins: 4
            currentTime: overlayVM ? overlayVM.currentLapTime || "0:00.000" : "0:00.000"
            lastTime: overlayVM ? overlayVM.lastTime || "\u2014" : "\u2014"
            bestTime: overlayVM ? overlayVM.bestTime || "\u2014" : "\u2014"
            gap: ""
        }
    }

    OverlayWidget {
        visible: root.shouldShow("delta_bar")
        widgetId: "delta_bar"
        width: root.ws("delta_bar", "width", 300)
        height: root.ws("delta_bar", "height", 60)
        opacity: root.ws("delta_bar", "opacity", 0.92)
        x: root.ws("delta_bar", "x", 400); y: root.ws("delta_bar", "y", 20)
        fontScale: root.ws("delta_bar", "fontScale", 1.0)
        borderRadius: root.ws("delta_bar", "borderRadius", 12)
        Widgets.DeltaBarWidget {
            anchors.fill: parent; anchors.margins: 4
            delta: overlayVM ? overlayVM.liveDelta : 0
        }
    }

    OverlayWidget {
        visible: root.shouldShow("session_timer")
        widgetId: "session_timer"
        width: root.ws("session_timer", "width", 200)
        height: root.ws("session_timer", "height", 80)
        opacity: root.ws("session_timer", "opacity", 0.92)
        x: root.ws("session_timer", "x", 100); y: root.ws("session_timer", "y", 440)
        fontScale: root.ws("session_timer", "fontScale", 1.0)
        borderRadius: root.ws("session_timer", "borderRadius", 12)
        Widgets.SessionTimerWidget {
            anchors.fill: parent; anchors.margins: 4
            elapsed: overlayVM ? overlayVM.elapsed || "0:00" : "0:00"
            sessionType: overlayVM ? overlayVM.sessionType || "Practice" : "Practice"
            timeRemaining: ""
        }
    }

    OverlayWidget {
        visible: root.shouldShow("flags")
        widgetId: "flags"
        width: root.ws("flags", "width", 160)
        height: root.ws("flags", "height", 100)
        opacity: root.ws("flags", "opacity", 0.92)
        x: root.ws("flags", "x", 700); y: root.ws("flags", "y", 340)
        fontScale: root.ws("flags", "fontScale", 1.0)
        borderRadius: root.ws("flags", "borderRadius", 12)
        Widgets.FlagsWidget {
            anchors.fill: parent; anchors.margins: 4
            flag: overlayVM ? overlayVM.currentFlag || "green" : "green"
        }
    }

    OverlayWidget {
        visible: root.shouldShow("radar")
        widgetId: "radar"
        width: root.ws("radar", "width", 200)
        height: root.ws("radar", "height", 200)
        opacity: root.ws("radar", "opacity", 0.92)
        x: root.ws("radar", "x", 830); y: root.ws("radar", "y", 400)
        fontScale: root.ws("radar", "fontScale", 1.0)
        borderRadius: root.ws("radar", "borderRadius", 12)
        Widgets.RadarWidget {
            anchors.fill: parent; anchors.margins: 4
        }
    }

    OverlayWidget {
        visible: root.shouldShow("weather_monitor")
        widgetId: "weather_monitor"
        width: root.ws("weather_monitor", "width", 200)
        height: root.ws("weather_monitor", "height", 160)
        opacity: root.ws("weather_monitor", "opacity", 0.92)
        x: root.ws("weather_monitor", "x", 830); y: root.ws("weather_monitor", "y", 80)
        fontScale: root.ws("weather_monitor", "fontScale", 1.0)
        borderRadius: root.ws("weather_monitor", "borderRadius", 12)
        Widgets.WeatherMonitorWidget {
            anchors.fill: parent; anchors.margins: 4
            trackTemp: overlayVM ? overlayVM.trackTemp : 0
            airTemp: overlayVM ? overlayVM.airTemp : 0
        }
    }

    OverlayWidget {
        visible: root.shouldShow("gforce_meter_full")
        widgetId: "gforce_meter_full"
        width: root.ws("gforce_meter_full", "width", 200)
        height: root.ws("gforce_meter_full", "height", 200)
        opacity: root.ws("gforce_meter_full", "opacity", 0.92)
        x: root.ws("gforce_meter_full", "x", 20); y: root.ws("gforce_meter_full", "y", 20)
        fontScale: root.ws("gforce_meter_full", "fontScale", 1.0)
        borderRadius: root.ws("gforce_meter_full", "borderRadius", 12)
        Widgets.GForceMeterWidget {
            anchors.fill: parent; anchors.margins: 4
            latG: overlayVM ? overlayVM.latAccelG : 0
            longG: overlayVM ? overlayVM.longAccelG : 0
        }
    }

    OverlayWidget {
        visible: root.shouldShow("input_telemetry")
        widgetId: "input_telemetry"
        width: root.ws("input_telemetry", "width", 280)
        height: root.ws("input_telemetry", "height", 180)
        opacity: root.ws("input_telemetry", "opacity", 0.92)
        x: root.ws("input_telemetry", "x", 440); y: root.ws("input_telemetry", "y", 360)
        fontScale: root.ws("input_telemetry", "fontScale", 1.0)
        borderRadius: root.ws("input_telemetry", "borderRadius", 12)
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

    OverlayWidget {
        visible: root.shouldShow("fuel_calculator")
        widgetId: "fuel_calculator"
        width: root.ws("fuel_calculator", "width", 220)
        height: root.ws("fuel_calculator", "height", 200)
        opacity: root.ws("fuel_calculator", "opacity", 0.92)
        x: root.ws("fuel_calculator", "x", 20); y: root.ws("fuel_calculator", "y", 240)
        fontScale: root.ws("fuel_calculator", "fontScale", 1.0)
        borderRadius: root.ws("fuel_calculator", "borderRadius", 12)
        Widgets.FuelCalculatorWidget {
            anchors.fill: parent; anchors.margins: 4
            fuelLevel: overlayVM ? overlayVM.fuelLevel : 0
            fuelPerLap: overlayVM ? overlayVM.fuelPerLap : 0
            lapsLeft: overlayVM ? overlayVM.fuelLapsLeft : 0
        }
    }
}
