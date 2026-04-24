"""Live telemetry processing pipeline for the overlay HUD.

Composes the three :class:`LiveProcessor` sub-processors
(:class:`CoachingLiveProcessor`, :class:`DashboardLiveProcessor`,
:class:`InputDiagnosticsProcessor`) into a single ``process()`` call
that returns the aggregated overlay state the ``OverlayViewModel``
consumes (sprint T006).

Reproduce import audit (sprint T001) with
``python -c "import lap_coach_logger.core.live_telemetry_processor"``.
"""

from __future__ import annotations

import logging
from typing import Any

from lap_coach_logger.coaching.corner_insights import (
    CornerInsight,
    analyze_corner_comparisons,
)
from lap_coach_logger.core.coaching_live_processor import CoachingLiveProcessor
from lap_coach_logger.core.dashboard_live_processor import DashboardLiveProcessor
from lap_coach_logger.core.input_diagnostics_processor import (
    InputDiagnosticsProcessor,
)
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.telemetry_utils import to_float as _float

log = logging.getLogger(__name__)


def _build_sample_from_live(
    live: dict[str, Any], snap: dict[str, Any]
) -> TelemetrySample:
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
    """Composes the three LiveProcessor sub-processors into one pipeline."""

    # -- Lockup / wheelspin heuristic thresholds --------------------------------
    _LOCKUP_BRAKE_MIN: float = 0.8
    _LOCKUP_SPEED_MIN_KPH: float = 30.0
    _LOCKUP_LONG_G_MIN: float = 0.8  # hard deceleration (positive = braking)

    _WHEELSPIN_THROTTLE_MIN: float = 0.7
    _WHEELSPIN_LAT_G_MIN: float = 0.3
    _WHEELSPIN_SPEED_MIN_KPH: float = 20.0

    def __init__(self) -> None:
        self._coaching = CoachingLiveProcessor()
        self._dashboard = DashboardLiveProcessor()
        self._input = InputDiagnosticsProcessor()
        # Cache last published insights so we can detect lap-boundary
        # transitions without re-running the analyser every snapshot.
        self._last_insights_lap: int | None = None
        self._last_insights: list[CornerInsight] = []

    def process(self, live_dict: dict[str, Any], snap: dict[str, Any]) -> dict[str, Any]:
        """Process a raw snapshot, return aggregated overlay state."""
        sample = _build_sample_from_live(live_dict, snap)
        derived = snap.get("derived")

        # Fan the sample through the three sub-processors via the ABC.
        for sub in (self._dashboard, self._coaching, self._input):
            sub.on_sample(sample, dashboard_state=live_dict, derived_state=derived)

        dash = self._dashboard.snapshot()
        coach = self._coaching.snapshot()
        inp = self._input.snapshot()

        # Corner insights — recompute only on lap boundary.
        lap_tracker = self._dashboard._lap_tracker  # noqa: SLF001
        last_profile = lap_tracker._last_profile  # noqa: SLF001
        best_profile = lap_tracker._best_profile  # noqa: SLF001
        if last_profile is not None and last_profile.lap_number != self._last_insights_lap:
            self._last_insights = analyze_corner_comparisons(last_profile, best_profile)
            self._last_insights_lap = last_profile.lap_number

        return {
            "live_delta_s": dash["live_delta_s"],
            "best_lap_time_s": dash["best_lap_time_s"],
            "last_lap_time_s": dash["last_lap_time_s"],
            "current_lap_time_s": dash["current_lap_time_s"],
            "best_lap_time_fmt": dash["best_lap_time_fmt"],
            "last_lap_time_fmt": dash["last_lap_time_fmt"],
            "current_lap_time_fmt": dash["current_lap_time_fmt"],
            "sector_rows": dash["sector_rows"],
            "corner_rows": dash["corner_rows"],
            "tire_state": dash["tire_state"],
            "lockup_active": self._detect_lockup(sample),
            "wheelspin_active": self._detect_wheelspin(sample),
            "coaching_cards": coach["cards"],
            "input_smoothness": inp["smoothness"],
            "corner_insights": list(self._last_insights),
            "corner_insights_lap": self._last_insights_lap,
        }

    # -- heuristic helpers -----------------------------------------------------

    def _detect_lockup(self, sample: TelemetrySample) -> bool:
        """Lockup: heavy braking at speed with strong longitudinal deceleration."""
        brake = sample.brake_pct
        speed = sample.speed_kph
        long_g = sample.long_accel_g
        if brake is None or speed is None or long_g is None:
            return False
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

    def reset(self) -> None:
        """Reset all sub-processors (new session)."""
        self._coaching.on_session_end()
        self._dashboard.on_session_end()
        self._input.on_session_end()
        self._last_insights_lap = None
        self._last_insights = []


def _int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None
