"""Live telemetry processing pipeline for the overlay HUD.

Composes tracker instances (lap comparison, corner tracking) into a
single ``process()`` call that returns aggregated overlay state.
"""

from __future__ import annotations

import logging
from typing import Any

from lap_coach_logger.core.live_lap_compare import LiveLapComparisonTracker
from lap_coach_logger.core.schema import TelemetrySample

log = logging.getLogger(__name__)


def _format_lap_time(seconds: float | None) -> str:
    """Format seconds as ``M:SS.mmm`` or empty string when unavailable."""
    if seconds is None or seconds <= 0:
        return ""
    minutes = int(seconds) // 60
    remainder = seconds - minutes * 60
    return f"{minutes}:{remainder:06.3f}"


def _build_sample_from_live(live: dict[str, Any], snap: dict[str, Any]) -> TelemetrySample:
    """Construct a TelemetrySample from the coordinator snapshot dicts."""
    return TelemetrySample(
        sim=str(snap.get("sim") or ""),
        session_uid=str(live.get("session_uid") or snap.get("session_uid") or ""),
        session_time_s=_float(live.get("session_time_s")),
        lap_number=_int(live.get("lap_number") or live.get("current_lap")),
        lap_distance_m=_float(live.get("lap_distance_m")),
        lap_dist_pct=_float(live.get("lap_dist_pct")),
        speed_kph=_float(live.get("speed_kph")),
        throttle_pct=_float(live.get("throttle_pct")),
        brake_pct=_float(live.get("brake_pct")),
        steering_deg=_float(live.get("steering_deg")),
        gear=_int(live.get("gear")),
        rpm=_float(live.get("rpm")),
        world_pos_x=_float(live.get("world_pos_x")),
        world_pos_y=_float(live.get("world_pos_y")),
        world_pos_z=_float(live.get("world_pos_z")),
        long_accel_g=_float(live.get("long_accel_g")),
        lat_accel_g=_float(live.get("lat_accel_g")),
        fuel_level=_float(live.get("fuel_level")),
        track_name=str(live.get("track_name") or ""),
        car_name=str(live.get("car_name") or ""),
    )


class LiveTelemetryProcessor:
    """Composes live analysis trackers into a single processing pipeline."""

    def __init__(self) -> None:
        self._lap_tracker = LiveLapComparisonTracker()

    def process(self, live_dict: dict[str, Any], snap: dict[str, Any]) -> dict[str, Any]:
        """Process a raw snapshot, return aggregated overlay state.

        Returns dict with keys:
        - ``live_delta_s``: float -- current vs best delta in seconds
        - ``best_lap_time_s``: float | None
        - ``last_lap_time_s``: float | None
        - ``current_lap_time_s``: float | None
        - ``best_lap_time_fmt``: str -- formatted best lap time
        - ``last_lap_time_fmt``: str -- formatted last lap time
        - ``current_lap_time_fmt``: str -- formatted current lap elapsed
        - ``sector_rows``: list of dicts
        """
        sample = _build_sample_from_live(live_dict, snap)

        # Feed the sample into the lap comparison tracker.
        # dashboard_state can carry sector splits from the sim.
        self._lap_tracker.push_sample(
            sample,
            dashboard_state=live_dict,
            derived_state=snap.get("derived"),
        )

        # Pull the full comparison snapshot.
        compare = self._lap_tracker.snapshot()

        live_delta_s = compare.get("current_vs_best_delta_s") or 0.0
        best_lap_time_s = compare.get("best_lap_time_s")
        current_lap_time_s = compare.get("current_lap_time_s")

        # last_lap_time_s comes from the tracker's last finalized profile.
        last_profile = self._lap_tracker._last_profile
        last_lap_time_s = last_profile.lap_time_s if last_profile else None

        return {
            "live_delta_s": live_delta_s,
            "best_lap_time_s": best_lap_time_s,
            "last_lap_time_s": last_lap_time_s,
            "current_lap_time_s": current_lap_time_s,
            "best_lap_time_fmt": _format_lap_time(best_lap_time_s),
            "last_lap_time_fmt": _format_lap_time(last_lap_time_s),
            "current_lap_time_fmt": _format_lap_time(current_lap_time_s),
            "sector_rows": compare.get("sector_rows", []),
        }

    def reset(self) -> None:
        """Reset all trackers (new session)."""
        self._lap_tracker.reset()


# -- tiny helpers (avoid importing from other modules) -------------------------

def _float(value: object) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    return float(value)


def _int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None
