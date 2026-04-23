"""Pure-function helpers for OverlayViewModel data formatting."""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Overlay tiers (product redesign v2)
# ---------------------------------------------------------------------------
# Widgets not listed here default to "optional".

OVERLAY_TIERS: dict[str, str] = {
    # -- core_race: always visible in the main overlay catalog ---------------
    "delta_bar":        "core_race",
    "sector_delta":     "core_race",     # NEW: per-sector S1/S2/S3 deltas
    "lap_timing":       "core_race",
    "pit_countdown":    "core_race",     # NEW: "PIT IN 3" / "BOX BOX BOX"
    "strategy_status":  "core_race",     # NEW: compact strategy one-liner
    "fuel_strategy":    "core_race",
    "tire_life":        "core_race",
    "push_manage":      "core_race",     # NEW: PUSH/MANAGE/SAVE indicator
    "radar":            "core_race",
    "blind_spot":       "core_race",
    "gap_timing":       "core_race",     # NEW: "+1.2s to P4, -0.8s to P6"
    "race_reminder":    "core_race",     # NEW: unified coaching surface card
    "standings":        "core_race",
    "flags":            "core_race",
    "track_map":        "core_race",
    "session_timer":    "core_race",
    # -- coaching: shown by default in coaching mode -------------------------
    "delta_timing":     "coaching",
    "inputs_grip":      "coaching",
    "coaching":         "coaching",
    "input_telemetry":  "coaching",
    # -- optional: hidden from default catalog, accessible via settings ------
    # (everything else is optional by default — see the tier lookup below)
}


def get_widget_tier(widget_id: str) -> str:
    """Return the tier for a widget: 'core_race', 'coaching', or 'optional'."""
    return OVERLAY_TIERS.get(widget_id, "optional")


def is_widget_visible_in_catalog(widget_id: str, show_optional: bool = False) -> bool:
    """Whether a widget appears in the overlay manager's catalog.

    Core and coaching widgets always appear. Optional/streamer widgets
    only appear when the user has enabled 'Show Optional Pack' in settings.
    """
    tier = get_widget_tier(widget_id)
    if tier in ("core_race", "coaching"):
        return True
    return show_optional


WIDGET_CATEGORIES: dict[str, str] = {
    "delta_timing": "timing",
    "inputs_grip": "inputs",
    "fuel_strategy": "strategy",
    "coaching": "awareness",
    "gforce_meter": "inputs",
    "lap_timing": "timing",
    "track_map": "awareness",
    "standings": "awareness",
    "weather": "awareness",
    "laptime_graph": "timing",
    "laptime_log": "timing",
    "laptime_spread": "timing",
    "session_timer": "awareness",
    "delta_bar": "timing",
    "flags": "awareness",
    "digiflag": "awareness",
    "radar": "awareness",
    "radar_bars": "awareness",
    "blind_spot": "awareness",
    "overtake_alert": "awareness",
    "relatives": "awareness",
    "standings_table": "awareness",
    "leaderboard": "awareness",
    "head_to_head": "awareness",
    "track_map_canvas": "awareness",
    "mini_map": "awareness",
    "flat_map": "awareness",
    "fuel_calculator": "strategy",
    "race_strategy": "strategy",
    "tire_life": "strategy",
    "pitbox_helper": "strategy",
    "weather_monitor": "awareness",
    "boost_box": "inputs",
    "gforce_meter_full": "inputs",
    "advanced_panel": "inputs",
    "data_blocks": "inputs",
    "race_schedule": "awareness",
    "world_map": "awareness",
    "heart_rate": "inputs",
    "input_telemetry": "inputs",
    "chat": "streaming",
    "chat_highlight": "streaming",
    "chat_race_game": "streaming",
    "chat_race_standing": "streaming",
    "custom_text": "streaming",
    "custom_url": "streaming",
    "garage_cover": "streaming",
    "mic_visualizer": "streaming",
    "promo_code_alert": "streaming",
    # -- New core widgets (product redesign v2) ---
    "sector_delta": "timing",
    "pit_countdown": "strategy",
    "strategy_status": "strategy",
    "push_manage": "strategy",
    "gap_timing": "awareness",
    # -- Race coaching reminder (Surface Unification sprint) ---
    "race_reminder": "awareness",
}


def _ws(enabled: bool, w: int, h: int, hz: int = 30) -> dict:
    return {"enabled": enabled, "width": w, "height": h, "opacity": 0.92, "font_scale": 1.0, "refresh_hz": hz, "border_radius": 12}


def make_default_widget_settings() -> dict[str, dict]:
    return {
        "delta_timing": _ws(False, 320, 200, 60),
        "inputs_grip": _ws(False, 240, 260, 60),
        "fuel_strategy": _ws(False, 180, 240, 60),
        "coaching": _ws(False, 290, 200, 60),
        "gforce_meter": _ws(False, 200, 200, 60),
        "lap_timing": _ws(False, 280, 120, 60),
        "track_map": _ws(False, 240, 240),
        "standings": _ws(False, 300, 300),
        "weather": _ws(False, 200, 160),
        "laptime_graph": _ws(False, 320, 180),
        "laptime_log": _ws(False, 280, 200),
        "laptime_spread": _ws(False, 300, 160),
        "session_timer": _ws(False, 200, 80),
        "delta_bar": _ws(False, 300, 60, 60),
        "flags": _ws(False, 160, 100),
        "digiflag": _ws(False, 120, 120),
        "radar": _ws(False, 200, 200),
        "radar_bars": _ws(False, 200, 120),
        "blind_spot": _ws(False, 160, 80),
        "overtake_alert": _ws(False, 240, 60),
        "relatives": _ws(False, 280, 240),
        "standings_table": _ws(False, 280, 300),
        "leaderboard": _ws(False, 260, 280),
        "head_to_head": _ws(False, 300, 160),
        "track_map_canvas": _ws(False, 240, 240),
        "mini_map": _ws(False, 180, 180),
        "flat_map": _ws(False, 300, 100),
        "fuel_calculator": _ws(False, 220, 200),
        "race_strategy": _ws(False, 280, 200),
        "tire_life": _ws(False, 220, 180),
        "pitbox_helper": _ws(False, 240, 160),
        "weather_monitor": _ws(False, 200, 160),
        "boost_box": _ws(False, 160, 100),
        "gforce_meter_full": _ws(False, 200, 200, 60),
        "advanced_panel": _ws(False, 360, 280),
        "data_blocks": _ws(False, 320, 200),
        "race_schedule": _ws(False, 300, 240),
        "world_map": _ws(False, 280, 160),
        "heart_rate": _ws(False, 180, 100),
        "input_telemetry": _ws(False, 280, 180, 60),
        "chat": _ws(False, 280, 200),
        "chat_highlight": _ws(False, 320, 80),
        "chat_race_game": _ws(False, 280, 200),
        "chat_race_standing": _ws(False, 260, 240),
        "custom_text": _ws(False, 280, 60),
        "custom_url": _ws(False, 300, 200),
        "garage_cover": _ws(False, 320, 180),
        "mic_visualizer": _ws(False, 200, 60),
        "promo_code_alert": _ws(False, 300, 100),
        # -- New core widgets (product redesign v2) ---
        "sector_delta": _ws(False, 300, 60, 30),
        "pit_countdown": _ws(False, 240, 80, 30),
        "strategy_status": _ws(False, 400, 40, 30),
        "push_manage": _ws(False, 200, 60, 30),
        "gap_timing": _ws(False, 280, 60, 30),
        # -- Race coaching reminder card (bound to coachingSurface*) ---
        "race_reminder": _ws(False, 320, 64, 30),
    }


ACCENT_COLORS: dict[str, str] = {
    "purple": "#8B5CF6",
    "orange": "#C9A84C",
    "green": "#22C55E",
    "red": "#FF2A2A",
    "blue": "#3B82F6",
    "cyan": "#06B6D4",
}

LAYOUT_PRESETS: dict[str, dict[str, dict]] = {
    "qualifying": {
        "delta_timing": {"enabled": True, "x": 500, "y": 20, "width": 320, "height": 200},
        "lap_timing": {"enabled": True, "x": 830, "y": 20, "width": 280, "height": 120},
        "inputs_grip": {"enabled": True, "x": 20, "y": 400, "width": 240, "height": 260},
        "gforce_meter": {"enabled": True, "x": 20, "y": 20, "width": 200, "height": 200},
    },
    "race": {
        "delta_timing": {"enabled": True, "x": 500, "y": 20},
        "fuel_strategy": {"enabled": True, "x": 20, "y": 20, "width": 180, "height": 240},
        "radar": {"enabled": True, "x": 830, "y": 400, "width": 200, "height": 200},
        "standings": {"enabled": True, "x": 830, "y": 20, "width": 280, "height": 300},
        "blind_spot": {"enabled": True, "x": 500, "y": 680, "width": 160, "height": 80},
    },
    "streaming": {
        "delta_bar": {"enabled": True, "x": 400, "y": 20, "width": 300, "height": 60},
        "leaderboard": {"enabled": True, "x": 20, "y": 20, "width": 260, "height": 280},
        "chat": {"enabled": True, "x": 20, "y": 400, "width": 280, "height": 200},
        "chat_highlight": {"enabled": True, "x": 400, "y": 620, "width": 320, "height": 80},
        "custom_text": {"enabled": True, "x": 400, "y": 700, "width": 280, "height": 60},
    },
    "minimal": {
        "delta_timing": {"enabled": True, "x": 500, "y": 20, "width": 310, "height": 200},
    },
}


PRESET_LIST = [
    {"id": "qualifying", "name": "Qualifying Focus", "description": "Delta, timing, inputs, G-force"},
    {"id": "race", "name": "Race Focus", "description": "Delta, fuel, radar, standings, blind spot"},
    {"id": "streaming", "name": "Streaming", "description": "Delta bar, leaderboard, chat, highlights"},
    {"id": "minimal", "name": "Minimal", "description": "Delta timing only"},
]


def get_widget_int(settings: dict[str, dict], widget_id: str, key: str, default: int) -> int:
    s = settings.get(widget_id)
    return int(s.get(key, default)) if s else default


def get_widget_float(settings: dict[str, dict], widget_id: str, key: str, default: float) -> float:
    s = settings.get(widget_id)
    return float(s.get(key, default)) if s else default


def compute_scaled_widget(defaults: dict, scale: float) -> dict:
    scale = max(0.5, min(2.0, float(scale)))
    base_w = defaults.get("width", 300)
    base_h = defaults.get("height", 200)
    base_r = defaults.get("border_radius", 12)
    return {
        "scale": round(scale, 2),
        "width": int(base_w * scale),
        "height": int(base_h * scale),
        "border_radius": max(0, int(base_r * scale)),
    }


def extract_telemetry_inputs(live: dict) -> dict:
    """Extract and coerce telemetry input values from a live snapshot dict."""
    return {
        "speed_kph": float(live.get("speed_kph", 0.0)),
        "throttle_pct": float(live.get("throttle_pct", 0.0)),
        "brake_pct": float(live.get("brake_pct", 0.0)),
        "steering_deg": float(live.get("steering_deg", 0.0)),
        "lat_accel_g": float(live.get("lat_accel_g", 0.0)),
        "long_accel_g": float(live.get("long_accel_g", 0.0)),
        "clutch_pct": float(live.get("clutch_pct", 0.0)),
        "lap_dist_pct": float(live.get("lap_dist_pct") or 0.0),
        "lap_number": int(live.get("lap_number") or live.get("current_lap", 0)),
        "gear": int(live.get("gear", 0)),
        "rpm": int(live.get("rpm", 0)),
        "position": int(live.get("position") or 0),
        "num_cars": int(live.get("num_cars") or 0),
    }


def calc_tyre_temp_avg(live: dict) -> float:
    """Average tyre temperature across all four corners (non-None only)."""
    tyre_temps = [
        live.get("tyre_temp_lf"), live.get("tyre_temp_rf"),
        live.get("tyre_temp_lr"), live.get("tyre_temp_rr"),
    ]
    valid = [float(t) for t in tyre_temps if t is not None]
    return round(sum(valid) / len(valid), 1) if valid else 0.0


def calc_brake_temp_max(live: dict) -> float:
    """Maximum brake temperature across all four corners (non-None only)."""
    brake_temps = [
        live.get("brake_temp_lf"), live.get("brake_temp_rf"),
        live.get("brake_temp_lr"), live.get("brake_temp_rr"),
    ]
    valid = [float(t) for t in brake_temps if t is not None]
    return round(max(valid), 1) if valid else 0.0


def build_sector_states(raw_sectors: list[dict], dist_pct: float) -> list[dict]:
    """Convert processor sector rows into the QML-bindable format.

    Returns a list of ``{id, delta, status}`` dicts.  Falls back to
    three pending sectors when *raw_sectors* is empty.
    """
    new_sectors: list[dict] = []
    for i, row in enumerate(raw_sectors):
        sector_index = i + 1
        delta = row.get("delta_s") or 0
        current_time = row.get("current_time_s")
        marker = row.get("marker")

        sector_start = i / 3.0
        sector_end = (i + 1) / 3.0
        in_sector = sector_start <= dist_pct < sector_end

        if current_time is not None and marker is not None:
            if marker == "GAIN":
                status = "gain"
            elif marker == "LOSS":
                status = "loss"
            else:
                status = "gain"  # HOLD treated as neutral-gain
        elif in_sector:
            status = "active"
        else:
            status = "pending"

        new_sectors.append({
            "id": sector_index,
            "delta": round(delta, 3),
            "status": status,
        })

    if not new_sectors:
        new_sectors = [
            {"id": k, "delta": 0, "status": "pending"} for k in range(1, 4)
        ]

    return new_sectors


def extract_context(live: dict, snap: dict) -> dict:
    """Extract context fields (track, car, session info, flags) from snapshot."""
    is_recording = str(snap.get("status", "")).lower() == "recording"
    track = str(live.get("track_name") or snap.get("track") or snap.get("sim") or "")
    car = str(live.get("car_name") or snap.get("car") or "")
    session_type = str(live.get("session_type") or "")
    track_length_m = float(live.get("track_length_m") or 0.0)
    track_temp = float(live.get("track_temp_c") or 0.0)
    air_temp = float(live.get("air_temp_c") or 0.0)

    is_in_pits = bool(live.get("is_in_pits"))
    is_on_track = bool(live.get("is_on_track"))
    if is_in_pits and not is_on_track:
        current_flag = "none"
    elif is_recording and is_on_track:
        current_flag = "green"
    else:
        current_flag = "none"

    return {
        "track": track,
        "car": car,
        "is_recording": is_recording,
        "session_type": session_type,
        "track_length_m": track_length_m,
        "track_temp": track_temp,
        "air_temp": air_temp,
        "current_flag": current_flag,
    }


def calc_fuel_state(
    fuel: float,
    prev_fuel_level: float,
    lap_fuel_samples: list[float],
    lap_number: int,
    total_laps: int,
) -> dict:
    """Calculate fuel metrics from current fuel level and history.

    Returns a dict with fuel_level, fuel_per_lap, fuel_laps_left,
    fuel_state, prev_fuel_level, and the (possibly updated) lap_fuel_samples list.
    """
    result: dict = {
        "fuel_level": fuel,
        "fuel_per_lap": 0.0,
        "fuel_laps_left": 0.0,
        "fuel_state": "SAFE",
        "prev_fuel_level": prev_fuel_level,
        "lap_fuel_samples": lap_fuel_samples,
        "changed": False,
    }
    if fuel <= 0:
        return result

    samples = list(lap_fuel_samples)
    if prev_fuel_level > 0 and fuel < prev_fuel_level:
        consumed = prev_fuel_level - fuel
        if 0.1 < consumed < 20:
            samples.append(consumed)
            if len(samples) > 10:
                samples.pop(0)

    result["prev_fuel_level"] = fuel
    result["fuel_level"] = fuel
    result["lap_fuel_samples"] = samples

    if samples:
        avg = sum(samples) / len(samples)
        result["fuel_per_lap"] = round(avg, 2)
        result["fuel_laps_left"] = round(fuel / avg, 1) if avg > 0 else 0.0

        laps_remaining = total_laps - lap_number
        if laps_remaining <= 0:
            laps_remaining = 99
        fuel_laps_left = result["fuel_laps_left"]
        if fuel_laps_left < 1.5:
            result["fuel_state"] = "BOX"
        elif fuel_laps_left < laps_remaining * 0.85:
            result["fuel_state"] = "SAVE"
        elif fuel_laps_left < laps_remaining * 1.05:
            result["fuel_state"] = "TIGHT"
        else:
            result["fuel_state"] = "SAFE"

    result["changed"] = True
    return result


def extract_coaching_top_card(cards: list[dict]) -> dict:
    """Extract display fields from the top coaching card."""
    if not cards:
        return {
            "visible": False,
            "headline": "",
            "sub": "",
            "category": "",
            "severity": "positive",
            "confidence": 0,
            "sector": "",
        }
    top = cards[0]
    return {
        "visible": True,
        "headline": str(top.get("headline", "")),
        "sub": str(top.get("sub", "")),
        "category": str(top.get("category", "")),
        "severity": str(top.get("severity", "caution")),
        "confidence": int(top.get("confidence", 80)),
        "sector": str(top.get("sector", "")),
    }
