"""Live telemetry processing pipeline for the overlay HUD.

Composes tracker instances (lap comparison, corner tracking) into a
single ``process()`` call that returns aggregated overlay state.
"""

from __future__ import annotations

import logging
from typing import Any

from lap_coach_logger.core.live_coach import LiveCoachTracker
from lap_coach_logger.core.live_dashboard import LiveCornerTracker
from lap_coach_logger.core.live_input_diagnostics import LiveInputDiagnosticsTracker
from lap_coach_logger.core.live_lap_compare import LiveLapComparisonTracker
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.tire_model import TireDegradationTracker

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

    # -- Lockup / wheelspin heuristic thresholds --------------------------------
    _LOCKUP_BRAKE_MIN: float = 0.8
    _LOCKUP_SPEED_MIN_KPH: float = 30.0
    _LOCKUP_LONG_G_MIN: float = 0.8  # hard deceleration (positive = braking)

    _WHEELSPIN_THROTTLE_MIN: float = 0.7
    _WHEELSPIN_LAT_G_MIN: float = 0.3
    _WHEELSPIN_SPEED_MIN_KPH: float = 20.0

    def __init__(self) -> None:
        self._lap_tracker = LiveLapComparisonTracker()
        self._coach_tracker = LiveCoachTracker()
        self._input_tracker = LiveInputDiagnosticsTracker()
        self._corner_tracker = LiveCornerTracker()
        self._tire_tracker = TireDegradationTracker()

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

        # -- Lockup / wheelspin heuristic detection --------------------------
        lockup_active = self._detect_lockup(sample)
        wheelspin_active = self._detect_wheelspin(sample)

        # -- Coaching tracker ------------------------------------------------
        self._coach_tracker.push_sample(
            sample,
            dashboard_state=live_dict,
            derived_state=snap.get("derived"),
        )
        coach_snap = self._coach_tracker.snapshot()
        coaching_alerts = coach_snap.get("alerts", [])
        coaching_prompts = coach_snap.get("coaching", [])
        coaching_cards = self._build_coaching_cards(coaching_alerts, coaching_prompts)

        # -- Corner tracker (uses raw snapshot dict, not TelemetrySample) ------
        self._corner_tracker.push_snapshot(live_dict)
        corner_rows = self._corner_tracker.rows()

        # -- Tire degradation tracker ------------------------------------------
        tire_temps = (
            _float(live_dict.get("tyre_temp_lf")) or 0,
            _float(live_dict.get("tyre_temp_rf")) or 0,
            _float(live_dict.get("tyre_temp_lr")) or 0,
            _float(live_dict.get("tyre_temp_rr")) or 0,
        )
        lap_num = _int(live_dict.get("lap_number")) or 0
        if any(t > 0 for t in tire_temps) and lap_num > 0:
            self._tire_tracker.push_sample(tire_temps, lap_num)
        tire_state = self._tire_tracker.state.to_dict()

        # -- Input diagnostics -----------------------------------------------
        self._input_tracker.push_sample(
            sample,
            dashboard_state=live_dict,
            derived_state=snap.get("derived"),
        )
        input_snap = self._input_tracker.snapshot()
        input_smoothness = self._compute_smoothness(input_snap)

        return {
            "live_delta_s": live_delta_s,
            "best_lap_time_s": best_lap_time_s,
            "last_lap_time_s": last_lap_time_s,
            "current_lap_time_s": current_lap_time_s,
            "best_lap_time_fmt": _format_lap_time(best_lap_time_s),
            "last_lap_time_fmt": _format_lap_time(last_lap_time_s),
            "current_lap_time_fmt": _format_lap_time(current_lap_time_s),
            "sector_rows": compare.get("sector_rows", []),
            "lockup_active": lockup_active,
            "wheelspin_active": wheelspin_active,
            "coaching_cards": coaching_cards,
            "input_smoothness": input_smoothness,
            "corner_rows": corner_rows,
            "tire_state": tire_state,
        }

    # -- heuristic helpers -----------------------------------------------------

    def _detect_lockup(self, sample: TelemetrySample) -> bool:
        """Lockup: heavy braking at speed with strong longitudinal deceleration."""
        brake = sample.brake_pct
        speed = sample.speed_kph
        long_g = sample.long_accel_g
        if brake is None or speed is None or long_g is None:
            return False
        # long_accel_g is negative under braking in most sims; compare abs.
        return (
            brake >= self._LOCKUP_BRAKE_MIN
            and speed >= self._LOCKUP_SPEED_MIN_KPH
            and abs(long_g) >= self._LOCKUP_LONG_G_MIN
        )

    def _detect_wheelspin(self, sample: TelemetrySample) -> bool:
        """Wheelspin: high throttle with lateral slip at moderate speed."""
        throttle = sample.throttle_pct
        speed = sample.speed_kph
        lat_g = sample.lat_accel_g
        if throttle is None or speed is None or lat_g is None:
            return False
        return (
            throttle >= self._WHEELSPIN_THROTTLE_MIN
            and abs(lat_g) >= self._WHEELSPIN_LAT_G_MIN
            and speed >= self._WHEELSPIN_SPEED_MIN_KPH
        )

    @staticmethod
    def _build_coaching_cards(
        alerts: list[dict], prompts: list[dict],
    ) -> list[dict]:
        """Merge alerts and coaching prompts into a unified card list."""
        cards: list[dict] = []
        for alert in alerts:
            severity = str(alert.get("severity", "caution"))
            if severity == "error":
                severity = "critical"
            cards.append({
                "headline": str(alert.get("title", "")),
                "sub": str(alert.get("detail", "")),
                "category": "ALERT",
                "severity": severity,
                "confidence": 90,
                "sector": "",
            })
        for prompt in prompts:
            cards.append({
                "headline": str(prompt.get("title", "")),
                "sub": str(prompt.get("detail", "")),
                "category": "COACHING",
                "severity": "caution",
                "confidence": 80,
                "sector": str(prompt.get("corner", "")),
            })
        return cards

    @staticmethod
    def _compute_smoothness(input_snap: dict) -> float:
        """Derive a 0-1 smoothness score from input diagnostics."""
        rows = input_snap.get("rows", {})
        brake_score = rows.get("brake_trace", {}).get("score")
        throttle_score = rows.get("throttle_modulation", {}).get("score")
        scores = [s for s in (brake_score, throttle_score) if isinstance(s, (int, float))]
        if not scores:
            return 0.75  # default before enough data
        return max(0.0, min(1.0, sum(scores) / len(scores) / 100.0))

    def reset(self) -> None:
        """Reset all trackers (new session)."""
        self._lap_tracker.reset()
        self._coach_tracker.reset()
        self._input_tracker.reset()
        self._corner_tracker.reset()
        self._tire_tracker.reset()


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
