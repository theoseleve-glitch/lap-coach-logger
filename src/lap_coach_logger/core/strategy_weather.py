"""iRacing weather forecast parser for the strategy engine.

Converts iRacing session WeatherForecast data (time-based) into
lap-based ConditionWindow objects so the strategy engine can plan
compound choices and pit timing around weather changes.

Non-iRacing sims do not provide this data and skip this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class ConditionWindow:
    """A contiguous block of laps sharing the same track conditions."""

    start_lap: int
    end_lap: int
    track_temp_c: float
    precipitation: float  # 0.0 – 1.0
    track_state: str  # "dry" | "damp" | "wet"
    recommended_compound: str  # "soft" | "inter" | "wet"


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

_PRECIP_DRY = 0.15
_PRECIP_DAMP = 0.4


def _classify(precipitation: float) -> tuple[str, str]:
    """Return (track_state, recommended_compound) for a precipitation value."""
    if precipitation < _PRECIP_DRY:
        return "dry", "soft"
    if precipitation <= _PRECIP_DAMP:
        return "damp", "inter"
    return "wet", "wet"


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------


def parse_forecast(
    session_info: dict,
    lap_time_s: float,
    total_laps: int,
) -> list[ConditionWindow]:
    """Convert iRacing WeatherForecast entries to lap-based windows.

    Parameters
    ----------
    session_info:
        Must contain ``session_info["WeatherInfo"]["WeatherForecast"]`` — a
        list of dicts with keys ``"time"`` (seconds from session start),
        ``"temperature"`` (°C), and ``"precipitation"`` (0.0–1.0).
    lap_time_s:
        Estimated average lap time in seconds, used to convert forecast
        time-stamps into lap numbers.
    total_laps:
        Total race length in laps.

    Returns
    -------
    list[ConditionWindow]
        One window per distinct forecast segment, clamped to [1, total_laps].
        Returns ``[]`` when the forecast is empty or missing.
    """
    try:
        forecast = session_info["WeatherInfo"]["WeatherForecast"]
    except (KeyError, TypeError):
        return []

    if not forecast or lap_time_s <= 0 or total_laps <= 0:
        return []

    # Sort by time to guarantee ordering.
    entries = sorted(forecast, key=lambda e: e["time"])

    windows: list[ConditionWindow] = []

    for idx, entry in enumerate(entries):
        time_s: float = entry["time"]
        temperature: float = entry["temperature"]
        precipitation: float = entry["precipitation"]

        # Convert time to lap number (1-based).
        start_lap = max(1, math.floor(time_s / lap_time_s) + 1)

        # End lap: just before the next entry starts, or race end.
        if idx + 1 < len(entries):
            next_time_s = entries[idx + 1]["time"]
            end_lap = max(1, math.floor(next_time_s / lap_time_s))
        else:
            end_lap = total_laps

        # Clamp to race bounds.
        start_lap = min(start_lap, total_laps)
        end_lap = min(end_lap, total_laps)

        if start_lap > end_lap:
            continue

        track_state, compound = _classify(precipitation)

        windows.append(ConditionWindow(
            start_lap=start_lap,
            end_lap=end_lap,
            track_temp_c=temperature,
            precipitation=precipitation,
            track_state=track_state,
            recommended_compound=compound,
        ))

    return windows


def update_from_live(
    current_windows: list[ConditionWindow],
    precipitation: float,
    track_wetness: float,
    track_temp: float,
    current_lap: int,
) -> list[ConditionWindow]:
    """Adjust condition windows based on actual live telemetry.

    For the window that contains *current_lap*, replace its readings
    with actual sensor data.  Future windows are left unchanged so the
    strategy engine can still plan ahead.

    Parameters
    ----------
    current_windows:
        The existing list of forecast-based windows.
    precipitation:
        Actual current precipitation reading (0.0–1.0).
    track_wetness:
        Actual track wetness sensor value (unused for classification
        today but stored for future refinement).
    track_temp:
        Actual track temperature in °C.
    current_lap:
        The lap the car is currently on (1-based).

    Returns
    -------
    list[ConditionWindow]
        A new list with the current window updated.
    """
    if not current_windows:
        return []

    updated: list[ConditionWindow] = []

    for window in current_windows:
        if window.start_lap <= current_lap <= window.end_lap:
            track_state, compound = _classify(precipitation)
            updated.append(ConditionWindow(
                start_lap=window.start_lap,
                end_lap=window.end_lap,
                track_temp_c=track_temp,
                precipitation=precipitation,
                track_state=track_state,
                recommended_compound=compound,
            ))
        else:
            updated.append(ConditionWindow(
                start_lap=window.start_lap,
                end_lap=window.end_lap,
                track_temp_c=window.track_temp_c,
                precipitation=window.precipitation,
                track_state=window.track_state,
                recommended_compound=window.recommended_compound,
            ))

    return updated
