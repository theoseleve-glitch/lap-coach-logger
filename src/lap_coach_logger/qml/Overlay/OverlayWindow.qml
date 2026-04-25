import QtQuick
import "../Theme" as Theme
import "widgets" as Widgets

// Pre-declared overlay windows. NO polling timer.
// Visibility driven by a revision counter that increments on VM signals.
// x/y set ONCE in onCompleted, never re-bound.

Item {
    id: root

    // Revision counter — forces QML to re-evaluate visibility bindings
    property int _rev: 0
    Connections {
        target: overlayVM
        function onWidgetSettingsChanged() { root._rev++ }
    }

    // T153: minimal-click acknowledgment for the corner prompt.
    // Default key 'X'; any wheel-button bind that maps to that
    // key (Logitech G HUB, Fanatec, gamepad → keyboard) flows
    // through this single shortcut → VM slot seam.
    Shortcut {
        sequence: "X"
        context: Qt.ApplicationShortcut
        onActivated: { if (overlayVM) overlayVM.acknowledgeCornerPrompt() }
    }

    function isOn(wid) {
        void(_rev)
        if (!overlayVM) return false
        return overlayVM.isWidgetEnabled(wid) && overlayVM.shouldShowOverlays
    }

    // Read non-position settings (these CAN re-evaluate on _rev)
    function gw(wid, key, def) {
        void(_rev)
        if (!overlayVM) return def
        if (key === "width") return overlayVM.getWidgetWidth(wid)
        if (key === "height") return overlayVM.getWidgetHeight(wid)
        if (key === "opacity") return overlayVM.getWidgetOpacity(wid)
        if (key === "fontScale") return overlayVM.getWidgetFontScale(wid)
        if (key === "borderRadius") return overlayVM.getWidgetBorderRadius(wid)
        return def
    }

    // Base component: sets x/y ONCE on creation, never re-binds
    component OW: OverlayWidget {
        property string _wid: ""
        Component.onCompleted: {
            if (overlayVM && _wid) {
                x = overlayVM.getWidgetX(_wid)
                y = overlayVM.getWidgetY(_wid)
            }
        }
    }

    // ═══════════════════════════════════════════════════════════
    // 12 pre-declared overlay widgets
    // ═══════════════════════════════════════════════════════════

    OW {
        _wid: "delta_timing"; widgetId: "delta_timing"; category: "timing"
        visible: root.isOn("delta_timing")
        width: root.gw("delta_timing","width",320)
        height: root.gw("delta_timing","height",200)
        opacity: root.gw("delta_timing","opacity",0.92)
        fontScale: root.gw("delta_timing","fontScale",1.0)
        borderRadius: root.gw("delta_timing","borderRadius",12)
        Widgets.DeltaTimeWidget {
            anchors.fill: parent; anchors.margins: 4
            delta: overlayVM ? overlayVM.liveDelta : 0
            lapTime: overlayVM ? overlayVM.currentLapTime || "0:00.000" : "0:00.000"
            bestTime: overlayVM ? overlayVM.bestTime || "\u2014" : "\u2014"
            lapNumber: overlayVM ? overlayVM.lapNumber : 0
            totalLaps: 0
            lapProgress: overlayVM ? overlayVM.lapProgress : 0
            sectors: overlayVM ? overlayVM.sectorStates || [] : []
        }
    }

    OW {
        _wid: "inputs_grip"; widgetId: "inputs_grip"; category: "inputs"
        visible: root.isOn("inputs_grip")
        width: root.gw("inputs_grip","width",240)
        height: root.gw("inputs_grip","height",260)
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
        _wid: "fuel_strategy"; widgetId: "fuel_strategy"; category: "strategy"
        visible: root.isOn("fuel_strategy")
        width: root.gw("fuel_strategy","width",180)
        height: root.gw("fuel_strategy","height",240)
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
        _wid: "lap_timing"; widgetId: "lap_timing"; category: "timing"
        visible: root.isOn("lap_timing")
        width: root.gw("lap_timing","width",280)
        height: root.gw("lap_timing","height",120)
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
        _wid: "delta_bar"; widgetId: "delta_bar"; category: "timing"
        visible: root.isOn("delta_bar")
        width: root.gw("delta_bar","width",300)
        height: root.gw("delta_bar","height",60)
        opacity: root.gw("delta_bar","opacity",0.92)
        fontScale: root.gw("delta_bar","fontScale",1.0)
        borderRadius: root.gw("delta_bar","borderRadius",12)
        Widgets.DeltaBarWidget {
            anchors.fill: parent; anchors.margins: 4
            delta: overlayVM ? overlayVM.liveDelta : 0
        }
    }

    // -- Redesign v2: strategy + coaching widgets ----------------------------

    OW {
        _wid: "pit_countdown"; widgetId: "pit_countdown"; category: "strategy"
        // Only render when pit_countdown has content AND the user enabled it.
        // This keeps screen clean outside the pit window — even when enabled.
        visible: root.isOn("pit_countdown") && (overlayVM ? overlayVM.pitCountdownVisible : false)
        width: root.gw("pit_countdown","width",240)
        height: root.gw("pit_countdown","height",80)
        opacity: root.gw("pit_countdown","opacity",0.92)
        fontScale: root.gw("pit_countdown","fontScale",1.0)
        borderRadius: root.gw("pit_countdown","borderRadius",10)
        Widgets.PitCountdownWidget {
            anchors.fill: parent; anchors.margins: 4
            headline: overlayVM ? overlayVM.pitCountdownHeadline || "" : ""
            sub: overlayVM ? overlayVM.pitCountdownSub || "" : ""
            severity: overlayVM ? overlayVM.pitCountdownSeverity || "ok" : "ok"
        }
    }

    OW {
        _wid: "strategy_status"; widgetId: "strategy_status"; category: "strategy"
        visible: root.isOn("strategy_status")
        width: root.gw("strategy_status","width",400)
        height: root.gw("strategy_status","height",40)
        opacity: root.gw("strategy_status","opacity",0.92)
        fontScale: root.gw("strategy_status","fontScale",1.0)
        borderRadius: root.gw("strategy_status","borderRadius",8)
        Widgets.StrategyStatusWidget {
            anchors.fill: parent; anchors.margins: 4
            line: overlayVM ? overlayVM.strategyStatusLine || "" : ""
            severity: overlayVM ? overlayVM.strategyStatusSeverity || "ok" : "ok"
        }
    }

    OW {
        _wid: "sector_delta"; widgetId: "sector_delta"; category: "timing"
        visible: root.isOn("sector_delta")
        width: root.gw("sector_delta","width",300)
        height: root.gw("sector_delta","height",60)
        opacity: root.gw("sector_delta","opacity",0.92)
        fontScale: root.gw("sector_delta","fontScale",1.0)
        borderRadius: root.gw("sector_delta","borderRadius",8)
        Widgets.SectorDeltaWidget {
            anchors.fill: parent; anchors.margins: 4
            deltas: overlayVM ? overlayVM.sectorDeltas || [] : []
        }
    }

    OW {
        _wid: "push_manage"; widgetId: "push_manage"; category: "strategy"
        visible: root.isOn("push_manage")
        width: root.gw("push_manage","width",200)
        height: root.gw("push_manage","height",60)
        opacity: root.gw("push_manage","opacity",0.92)
        fontScale: root.gw("push_manage","fontScale",1.0)
        borderRadius: root.gw("push_manage","borderRadius",8)
        Widgets.PushManageWidget {
            anchors.fill: parent; anchors.margins: 4
            state: overlayVM ? overlayVM.pushManageState || "PUSH" : "PUSH"
            reason: overlayVM ? overlayVM.pushManageReason || "" : ""
        }
    }

    OW {
        _wid: "gap_timing"; widgetId: "gap_timing"; category: "awareness"
        visible: root.isOn("gap_timing")
        width: root.gw("gap_timing","width",280)
        height: root.gw("gap_timing","height",60)
        opacity: root.gw("gap_timing","opacity",0.92)
        fontScale: root.gw("gap_timing","fontScale",1.0)
        borderRadius: root.gw("gap_timing","borderRadius",8)
        Widgets.GapTimingWidget {
            anchors.fill: parent; anchors.margins: 4
            // NaN default means "no data" — widget renders degraded state
            gapAhead: overlayVM && overlayVM.gapAhead !== undefined ? overlayVM.gapAhead : NaN
            gapBehind: overlayVM && overlayVM.gapBehind !== undefined ? overlayVM.gapBehind : NaN
            positionAhead: overlayVM ? overlayVM.positionAhead || 0 : 0
            positionBehind: overlayVM ? overlayVM.positionBehind || 0 : 0
        }
    }

    OW {
        _wid: "race_reminder"; widgetId: "race_reminder"; category: "awareness"
        visible: root.isOn("race_reminder")
            && overlayVM
            && overlayVM.coachingSurfaceVisible === true
        width: root.gw("race_reminder","width",320)
        height: root.gw("race_reminder","height",64)
        opacity: root.gw("race_reminder","opacity",0.92)
        fontScale: root.gw("race_reminder","fontScale",1.0)
        borderRadius: root.gw("race_reminder","borderRadius",10)
        Widgets.RaceReminderWidget {
            anchors.fill: parent; anchors.margins: 4
            surfaceVisible: overlayVM ? overlayVM.coachingSurfaceVisible === true : false
            headline: overlayVM ? overlayVM.coachingSurfaceHeadline || "" : ""
            sub: overlayVM ? overlayVM.coachingSurfaceSub || "" : ""
            severity: overlayVM ? overlayVM.coachingSurfaceSeverity || "ok" : "ok"
            category: overlayVM ? overlayVM.coachingSurfaceCategory || "" : ""
            focus: overlayVM ? overlayVM.coachingSurfaceFocus || "" : ""
            freshness: overlayVM ? overlayVM.coachingSurfaceFreshness || "stale" : "stale"
            confidence: overlayVM ? overlayVM.techniqueConfidence || "low" : "low"
        }
    }

    OW {
        _wid: "session_timer"; widgetId: "session_timer"; category: "timing"
        visible: root.isOn("session_timer")
        width: root.gw("session_timer","width",200)
        height: root.gw("session_timer","height",80)
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
        _wid: "flags"; widgetId: "flags"; category: "awareness"
        visible: root.isOn("flags")
        width: root.gw("flags","width",160)
        height: root.gw("flags","height",100)
        opacity: root.gw("flags","opacity",0.92)
        fontScale: root.gw("flags","fontScale",1.0)
        borderRadius: root.gw("flags","borderRadius",12)
        Widgets.FlagsWidget {
            anchors.fill: parent; anchors.margins: 4
            flag: overlayVM ? overlayVM.currentFlag || "green" : "green"
        }
    }

    OW {
        _wid: "radar"; widgetId: "radar"; category: "awareness"
        visible: root.isOn("radar")
        width: root.gw("radar","width",200)
        height: root.gw("radar","height",200)
        opacity: root.gw("radar","opacity",0.92)
        fontScale: root.gw("radar","fontScale",1.0)
        borderRadius: root.gw("radar","borderRadius",12)
        Widgets.RadarWidget { anchors.fill: parent; anchors.margins: 4 }
    }

    OW {
        _wid: "weather_monitor"; widgetId: "weather_monitor"; category: "awareness"
        visible: root.isOn("weather_monitor")
        width: root.gw("weather_monitor","width",200)
        height: root.gw("weather_monitor","height",160)
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
        _wid: "gforce_meter_full"; widgetId: "gforce_meter_full"; category: "inputs"
        visible: root.isOn("gforce_meter_full")
        width: root.gw("gforce_meter_full","width",200)
        height: root.gw("gforce_meter_full","height",200)
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
        _wid: "input_telemetry"; widgetId: "input_telemetry"; category: "inputs"
        visible: root.isOn("input_telemetry")
        width: root.gw("input_telemetry","width",280)
        height: root.gw("input_telemetry","height",180)
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
        _wid: "race_strategy"; widgetId: "race_strategy"; category: "strategy"
        visible: root.isOn("race_strategy")
        width: root.gw("race_strategy","width",280)
        height: root.gw("race_strategy","height",200)
        opacity: root.gw("race_strategy","opacity",0.92)
        fontScale: root.gw("race_strategy","fontScale",1.0)
        borderRadius: root.gw("race_strategy","borderRadius",12)
        Widgets.RaceStrategyWidget {
            anchors.fill: parent; anchors.margins: 4
            nextPitLap: overlayVM ? overlayVM.strategyNextPitLap : 0
            fuelToAdd: overlayVM ? overlayVM.strategyFuelToAdd : 0
            stintsRemaining: overlayVM ? overlayVM.strategyStintsRemaining : 0
            pitStops: overlayVM ? overlayVM.strategyPitStops || [] : []
            fuelAtFinish: overlayVM ? overlayVM.strategyFuelAtFinish : 0
            totalLaps: overlayVM ? overlayVM.strategyTotalLaps : 0
            currentLap: overlayVM ? overlayVM.lapNumber : 0
            pitArmed: overlayVM ? overlayVM.pitArmed : false
            guidance: overlayVM ? overlayVM.strategyGuidance : ""
            decisionPrompt: overlayVM ? overlayVM.decisionPrompt : ""
            cornerPrompt: overlayVM ? overlayVM.cornerPrompt : ""
        }
    }

    OW {
        _wid: "fuel_calculator"; widgetId: "fuel_calculator"; category: "strategy"
        visible: root.isOn("fuel_calculator")
        width: root.gw("fuel_calculator","width",220)
        height: root.gw("fuel_calculator","height",200)
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

    OW {
        _wid: "tire_life"; widgetId: "tire_life"; category: "strategy"
        visible: root.isOn("tire_life")
        width: root.gw("tire_life","width",220)
        height: root.gw("tire_life","height",180)
        opacity: root.gw("tire_life","opacity",0.92)
        fontScale: root.gw("tire_life","fontScale",1.0)
        borderRadius: root.gw("tire_life","borderRadius",12)
        Widgets.TireLifeWidget {
            anchors.fill: parent; anchors.margins: 4
            gripPct: overlayVM ? overlayVM.tireGripPct : 100
            lapCount: overlayVM ? overlayVM.tireLapCount : 0
            lapsRemaining: overlayVM ? overlayVM.tireLapsRemaining : 99
            condition: overlayVM ? overlayVM.tireCondition : "good"
            tempLF: overlayVM ? overlayVM.tireTempLF : 0
            tempRF: overlayVM ? overlayVM.tireTempRF : 0
            tempLR: overlayVM ? overlayVM.tireTempLR : 0
            tempRR: overlayVM ? overlayVM.tireTempRR : 0
        }
    }

    // ── T171: Global "Coaching disabled — check backend" banner ─
    // Renders when the coaching backend is unavailable. Wired to
    // overlayVM.coachingDisabled — falsy default keeps the banner
    // hidden when the VM doesn't expose the property yet.
    Rectangle {
        id: coachingDisabledBanner
        visible: overlayVM ? !!overlayVM.coachingDisabled : false
        anchors {
            top: parent.top
            horizontalCenter: parent.horizontalCenter
            topMargin: 12
        }
        width: bannerText.implicitWidth + 24
        height: bannerText.implicitHeight + 12
        radius: 6
        color: Qt.rgba(Theme.Tokens.safetyRed.r, Theme.Tokens.safetyRed.g, Theme.Tokens.safetyRed.b, 0.18)
        border.width: 1
        border.color: Theme.Tokens.safetyRed
        z: 1000

        Text {
            id: bannerText
            anchors.centerIn: parent
            text: "Coaching disabled — check backend"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 11
            font.weight: Font.Bold
            font.letterSpacing: 0.6
            color: Theme.Tokens.safetyRed
        }
    }
}
