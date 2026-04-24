"""Dashboard live processor (sprint T004).

Composes the existing lap-comparison, corner, and tire-degradation
trackers behind the ``LiveProcessor`` ABC and exposes a single
normalized snapshot dict the overlay ``OverlayViewModel`` can
consume directly (mirrors the dashboard-relevant keys produced by
``LiveTelemetryProcessor.process`` today).
"""

from __future__ import annotations

from typing import Any

from lap_coach_logger.core.live_dashboard import LiveCornerTracker
from lap_coach_logger.core.live_lap_compare import LiveLapComparisonTracker
from lap_coach_logger.core.live_processor import LiveProcessor
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.telemetry_utils import to_float as _float
from lap_coach_logger.core.tire_model import TireDegradationTracker


class DashboardLiveProcessor(LiveProcessor):
    """Live dashboard sub-processor: lap delta, sectors, corners, tire state."""

    __slots__ = ("_lap_tracker", "_corner_tracker", "_tire_tracker", "_last_dash")

    def __init__(self) -> None:
        self._lap_tracker = LiveLapComparisonTracker()
        self._corner_tracker = LiveCornerTracker()
        self._tire_tracker = TireDegradationTracker()
        self._last_dash: dict[str, Any] = {}

    def on_sample(
        self,
        sample: TelemetrySample,
        *,
        dashboard_state: dict[str, Any] | None = None,
        derived_state: dict[str, Any] | None = None,
    ) -> None:
        self._lap_tracker.push_sample(
            sample,
            dashboard_state=dashboard_state,
            derived_state=derived_state,
        )
        # Corner tracker expects the raw snapshot dict, fall back to an
        # empty mapping if the caller doesn't pass one.
        self._corner_tracker.push_snapshot(dashboard_state or {})

        self._feed_tires(dashboard_state)

    def on_lap_end(self, lap_number: int, lap_time_s: float | None) -> None:
        # Lap trackers finalize on sample lap_number transitions.
        return None

    def on_session_end(self) -> None:
        self._lap_tracker.reset()
        self._corner_tracker.reset()
        self._tire_tracker.reset()
        self._last_dash = {}

    def snapshot(self) -> dict[str, Any]:
        compare = self._lap_tracker.snapshot()

        live_delta_s = float(compare.get("current_vs_best_delta_s") or 0.0)
        best_lap_time_s = compare.get("best_lap_time_s")
        current_lap_time_s = compare.get("current_lap_time_s")

        last_profile = self._lap_tracker._last_profile  # noqa: SLF001
        last_lap_time_s = last_profile.lap_time_s if last_profile else None

        return {
            "live_delta_s": live_delta_s,
            "best_lap_time_s": best_lap_time_s,
            "last_lap_time_s": last_lap_time_s,
            "current_lap_time_s": current_lap_time_s,
            "best_lap_time_fmt": _format_lap_time(best_lap_time_s),
            "last_lap_time_fmt": _format_lap_time(last_lap_time_s),
            "current_lap_time_fmt": _format_lap_time(current_lap_time_s),
            "sector_rows": list(compare.get("sector_rows", []) or []),
            "corner_rows": list(self._corner_tracker.rows()),
            "tire_state": self._tire_tracker.state.to_dict(),
        }

    def _feed_tires(self, dashboard_state: dict[str, Any] | None) -> None:
        if not dashboard_state:
            return
        temps = (
            _float(dashboard_state.get("tyre_temp_lf")) or 0,
            _float(dashboard_state.get("tyre_temp_rf")) or 0,
            _float(dashboard_state.get("tyre_temp_lr")) or 0,
            _float(dashboard_state.get("tyre_temp_rr")) or 0,
        )
        lap_num = _coerce_int(dashboard_state.get("lap_number")) or 0
        if any(t > 0 for t in temps) and lap_num > 0:
            self._tire_tracker.push_sample(temps, lap_num)


def _format_lap_time(seconds: float | None) -> str:
    if seconds is None or seconds <= 0:
        return ""
    minutes = int(seconds) // 60
    remainder = seconds - minutes * 60
    return f"{minutes}:{remainder:06.3f}"


def _coerce_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


__all__ = ["DashboardLiveProcessor"]
