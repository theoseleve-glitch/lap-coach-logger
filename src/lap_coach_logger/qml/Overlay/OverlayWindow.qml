import QtQuick
import "../Theme" as Theme
import "widgets" as Widgets

// Dynamic overlay manager.
// Iterates over ALL widget IDs in overlayVM.widgetSettings and
// creates / destroys independent, draggable OverlayWidget windows
// for each enabled widget.

Item {
    id: root

    property bool overlayVisible: false

    // Live map of widget_id -> OverlayWidget Window instance
    property var _windows: ({})

    // Widget-ID to Component mapping.
    // Every key in overlayVM._widget_settings must appear here.
    property var _componentMap: ({
        "delta_timing":       deltaTimingComp,
        "inputs_grip":        inputsGripComp,
        "fuel_strategy":      fuelStrategyComp,
        "coaching":           coachingComp,
        "gforce_meter":       gforceMeterComp,
        "lap_timing":         lapTimingComp,
        "track_map":          trackMapComp,
        "standings":          standingsComp,
        "weather":            weatherComp,
        "laptime_graph":      laptimeGraphComp,
        "laptime_log":        laptimeLogComp,
        "laptime_spread":     laptimeSpreadComp,
        "session_timer":      sessionTimerComp,
        "delta_bar":          deltaBarComp,
        "flags":              flagsComp,
        "digiflag":           digiflagComp,
        "radar":              radarComp,
        "radar_bars":         radarBarsComp,
        "blind_spot":         blindSpotComp,
        "overtake_alert":     overtakeAlertComp,
        "relatives":          relativesComp,
        "standings_table":    standingsTableComp,
        "leaderboard":        leaderboardComp,
        "head_to_head":       headToHeadComp,
        "track_map_canvas":   trackMapCanvasComp,
        "mini_map":           miniMapComp,
        "flat_map":           flatMapComp,
        "fuel_calculator":    fuelCalculatorComp,
        "pitbox_helper":      pitboxHelperComp,
        "weather_monitor":    weatherMonitorComp,
        "boost_box":          boostBoxComp,
        "gforce_meter_full":  gforceMeterFullComp,
        "advanced_panel":     advancedPanelComp,
        "data_blocks":        dataBlocksComp,
        "race_schedule":      raceScheduleComp,
        "world_map":          worldMapComp,
        "heart_rate":         heartRateComp,
        "input_telemetry":    inputTelemetryComp,
        "chat":               chatComp,
        "chat_highlight":     chatHighlightComp,
        "chat_race_game":     chatRaceGameComp,
        "chat_race_standing": chatRaceStandingComp,
        "custom_text":        customTextComp,
        "custom_url":         customUrlComp,
        "garage_cover":       garageCoverComp,
        "mic_visualizer":     micVisualizerComp,
        "promo_code_alert":   promoCodeAlertComp
    })

    onOverlayVisibleChanged: _syncWindows()

    Connections {
        target: overlayVM
        function onWidgetSettingsChanged() { root._syncWindows() }
    }

    function _syncWindows() {
        var ws = overlayVM ? overlayVM.widgetSettings : {}
        var ids = Object.keys(ws)

        for (var i = 0; i < ids.length; i++) {
            var wid = ids[i]
            var settings = ws[wid]
            var enabled = root.overlayVisible && settings && settings.enabled

            if (enabled && !_windows[wid]) {
                var comp = _componentMap[wid]
                if (comp) {
                    var win = comp.createObject(root, {
                        width:   settings.width   || 300,
                        height:  settings.height  || 200,
                        opacity: settings.opacity || 0.92,
                        x: 100 + (Object.keys(_windows).length % 6) * 40,
                        y:  80 + (Object.keys(_windows).length % 6) * 40
                    })
                    if (win) {
                        win.visible = true
                        _windows[wid] = win
                    }
                }
            } else if (!enabled && _windows[wid]) {
                _windows[wid].destroy()
                delete _windows[wid]
            } else if (enabled && _windows[wid]) {
                _windows[wid].width   = settings.width   || 300
                _windows[wid].height  = settings.height  || 200
                _windows[wid].opacity = settings.opacity || 0.92
            }
        }
    }

    // ================================================================
    //  Component declarations -- one per widget type
    // ================================================================

    // ── Delta / Timing ──
    Component {
        id: deltaTimingComp
        OverlayWidget {
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
    }

    // ── Inputs / Grip ──
    Component {
        id: inputsGripComp
        OverlayWidget {
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
    }

    // ── Fuel Strategy ──
    Component {
        id: fuelStrategyComp
        OverlayWidget {
            Widgets.FuelWidget {
                anchors.fill: parent; anchors.margins: 4
                remaining: overlayVM ? overlayVM.fuelLevel : 0
                lapsLeft: overlayVM ? overlayVM.fuelLapsLeft : 0
                fuelPerLap: overlayVM ? overlayVM.fuelPerLap : 0
                state: overlayVM ? overlayVM.fuelState || "SAFE" : "SAFE"
                pitWindow: ""
                totalLaps: 0
                currentLap: overlayVM ? overlayVM.lapNumber : 0
            }
        }
    }

    // ── Coaching ──
    Component {
        id: coachingComp
        OverlayWidget {
            Widgets.CoachingWidget {
                anchors.fill: parent; anchors.margins: 4
                headline: overlayVM ? overlayVM.coachingHeadline : ""
                sub: overlayVM ? overlayVM.coachingSub : ""
                category: overlayVM ? overlayVM.coachingCategory : ""
                severity: overlayVM ? overlayVM.coachingSeverity : "positive"
                confidence: overlayVM ? overlayVM.coachingConfidence : 0
                sector: overlayVM ? overlayVM.coachingSector : ""
            }
        }
    }

    // ── G-Force Meter ──
    Component {
        id: gforceMeterComp
        OverlayWidget {
            Widgets.GForceMeterWidget {
                anchors.fill: parent; anchors.margins: 4
                latG: overlayVM ? overlayVM.latAccelG : 0
                longG: overlayVM ? overlayVM.longAccelG : 0
            }
        }
    }

    // ── Lap Timing ──
    Component {
        id: lapTimingComp
        OverlayWidget {
            Widgets.LapTimingWidget {
                anchors.fill: parent; anchors.margins: 4
                currentTime: overlayVM ? overlayVM.currentLapTime : ""
                lastTime: overlayVM ? overlayVM.lastTime : ""
                bestTime: overlayVM ? overlayVM.bestTime : ""
                deltaVsBest: overlayVM ? overlayVM.lastDelta : ""
            }
        }
    }

    // ── Track Map ──
    Component {
        id: trackMapComp
        OverlayWidget {
            Widgets.TrackMapWidget {
                anchors.fill: parent; anchors.margins: 4
                carPosition: overlayVM ? overlayVM.lapDistPct : 0
            }
        }
    }

    // ── Standings ──
    Component {
        id: standingsComp
        OverlayWidget {
            Widgets.StandingsWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Weather ──
    Component {
        id: weatherComp
        OverlayWidget {
            Widgets.WeatherMonitorWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Laptime Graph ──
    Component {
        id: laptimeGraphComp
        OverlayWidget {
            Widgets.LaptimeGraphWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Laptime Log ──
    Component {
        id: laptimeLogComp
        OverlayWidget {
            Widgets.LaptimeLogWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Laptime Spread ──
    Component {
        id: laptimeSpreadComp
        OverlayWidget {
            Widgets.LaptimeSpreadWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Session Timer ──
    Component {
        id: sessionTimerComp
        OverlayWidget {
            Widgets.SessionTimerWidget {
                anchors.fill: parent; anchors.margins: 4
                elapsed: overlayVM ? overlayVM.elapsed || "0:00:00" : "0:00:00"
            }
        }
    }

    // ── Delta Bar ──
    Component {
        id: deltaBarComp
        OverlayWidget {
            Widgets.DeltaBarWidget {
                anchors.fill: parent; anchors.margins: 4
                delta: overlayVM ? overlayVM.liveDelta : 0
            }
        }
    }

    // ── Flags ──
    Component {
        id: flagsComp
        OverlayWidget {
            Widgets.FlagsWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Digiflag ──
    Component {
        id: digiflagComp
        OverlayWidget {
            Widgets.DigiflagWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Radar ──
    Component {
        id: radarComp
        OverlayWidget {
            Widgets.RadarWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Radar Bars ──
    Component {
        id: radarBarsComp
        OverlayWidget {
            Widgets.RadarBarsWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Blind Spot ──
    Component {
        id: blindSpotComp
        OverlayWidget {
            Widgets.BlindSpotWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Overtake Alert ──
    Component {
        id: overtakeAlertComp
        OverlayWidget {
            Widgets.OvertakeAlertWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Relatives ──
    Component {
        id: relativesComp
        OverlayWidget {
            Widgets.RelativesWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Standings Table ──
    Component {
        id: standingsTableComp
        OverlayWidget {
            Widgets.StandingsWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Leaderboard ──
    Component {
        id: leaderboardComp
        OverlayWidget {
            Widgets.LeaderboardWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Head to Head ──
    Component {
        id: headToHeadComp
        OverlayWidget {
            Widgets.HeadToHeadWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Track Map Canvas ──
    Component {
        id: trackMapCanvasComp
        OverlayWidget {
            Widgets.TrackMapWidget {
                anchors.fill: parent; anchors.margins: 4
                carPosition: overlayVM ? overlayVM.lapDistPct : 0
            }
        }
    }

    // ── Mini Map ──
    Component {
        id: miniMapComp
        OverlayWidget {
            Widgets.MiniMapWidget {
                anchors.fill: parent; anchors.margins: 4
                carPosition: overlayVM ? overlayVM.lapDistPct : 0
            }
        }
    }

    // ── Flat Map ──
    Component {
        id: flatMapComp
        OverlayWidget {
            Widgets.FlatMapWidget {
                anchors.fill: parent; anchors.margins: 4
                carPosition: overlayVM ? overlayVM.lapDistPct : 0
            }
        }
    }

    // ── Fuel Calculator ──
    Component {
        id: fuelCalculatorComp
        OverlayWidget {
            Widgets.FuelCalculatorWidget {
                anchors.fill: parent; anchors.margins: 4
                fuelLevel: overlayVM ? overlayVM.fuelLevel : 0
                fuelPerLap: overlayVM ? overlayVM.fuelPerLap : 0
                lapsLeft: overlayVM ? overlayVM.fuelLapsLeft : 0
            }
        }
    }

    // ── Pitbox Helper ──
    Component {
        id: pitboxHelperComp
        OverlayWidget {
            Widgets.PitboxHelperWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Weather Monitor ──
    Component {
        id: weatherMonitorComp
        OverlayWidget {
            Widgets.WeatherMonitorWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Boost Box ──
    Component {
        id: boostBoxComp
        OverlayWidget {
            Widgets.BoostBoxWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── G-Force Meter (Full) ──
    Component {
        id: gforceMeterFullComp
        OverlayWidget {
            Widgets.GForceMeterWidget {
                anchors.fill: parent; anchors.margins: 4
                latG: overlayVM ? overlayVM.latAccelG : 0
                longG: overlayVM ? overlayVM.longAccelG : 0
            }
        }
    }

    // ── Advanced Panel ──
    Component {
        id: advancedPanelComp
        OverlayWidget {
            Widgets.AdvancedPanelWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Data Blocks ──
    Component {
        id: dataBlocksComp
        OverlayWidget {
            Widgets.DataBlocksWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Race Schedule ──
    Component {
        id: raceScheduleComp
        OverlayWidget {
            Widgets.RaceScheduleWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── World Map ──
    Component {
        id: worldMapComp
        OverlayWidget {
            Widgets.WorldMapWidget {
                anchors.fill: parent; anchors.margins: 4
                trackName: overlayVM ? overlayVM.track : ""
            }
        }
    }

    // ── Heart Rate ──
    Component {
        id: heartRateComp
        OverlayWidget {
            Widgets.HeartRateWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Input Telemetry ──
    Component {
        id: inputTelemetryComp
        OverlayWidget {
            Widgets.InputTelemetryWidget {
                anchors.fill: parent; anchors.margins: 4
                throttle: overlayVM ? overlayVM.throttlePct : 0
                brake: overlayVM ? overlayVM.brakePct : 0
                steering: overlayVM ? overlayVM.steeringDeg / 450.0 : 0
                gear: overlayVM ? overlayVM.gear : 0
                rpm: overlayVM ? overlayVM.rpm : 0
            }
        }
    }

    // ── Chat ──
    Component {
        id: chatComp
        OverlayWidget {
            Widgets.ChatWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Chat Highlight ──
    Component {
        id: chatHighlightComp
        OverlayWidget {
            Widgets.ChatHighlightWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Chat Race Game ──
    Component {
        id: chatRaceGameComp
        OverlayWidget {
            Widgets.ChatRaceGameWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Chat Race Standing ──
    Component {
        id: chatRaceStandingComp
        OverlayWidget {
            Widgets.ChatRaceStandingWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Custom Text ──
    Component {
        id: customTextComp
        OverlayWidget {
            Widgets.CustomTextWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Custom URL ──
    Component {
        id: customUrlComp
        OverlayWidget {
            Widgets.CustomUrlWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Garage Cover ──
    Component {
        id: garageCoverComp
        OverlayWidget {
            Widgets.GarageCoverWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Mic Visualizer ──
    Component {
        id: micVisualizerComp
        OverlayWidget {
            Widgets.MicVisualizerWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }

    // ── Promo Code Alert ──
    Component {
        id: promoCodeAlertComp
        OverlayWidget {
            Widgets.PromoCodeAlertWidget {
                anchors.fill: parent; anchors.margins: 4
            }
        }
    }
}
