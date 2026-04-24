"""Input diagnostics live processor (sprint T005).

Wraps ``LiveInputDiagnosticsTracker`` behind the ``LiveProcessor`` ABC
and surfaces a compact snapshot (rows, flags, smoothness score) for
input-oriented overlay widgets (pedal trace, g-g, input linearity).
"""

from __future__ import annotations

from typing import Any

from lap_coach_logger.core.live_input_diagnostics import (
    LiveInputDiagnosticsTracker,
)
from lap_coach_logger.core.live_processor import LiveProcessor
from lap_coach_logger.core.schema import TelemetrySample


_DEFAULT_SMOOTHNESS = 0.75


class InputDiagnosticsProcessor(LiveProcessor):
    """Live input-diagnostics sub-processor."""

    __slots__ = ("_tracker",)

    def __init__(self) -> None:
        self._tracker = LiveInputDiagnosticsTracker()

    def on_sample(
        self,
        sample: TelemetrySample,
        *,
        dashboard_state: dict[str, Any] | None = None,
        derived_state: dict[str, Any] | None = None,
    ) -> None:
        self._tracker.push_sample(
            sample,
            dashboard_state=dashboard_state,
            derived_state=derived_state,
        )

    def on_lap_end(self, lap_number: int, lap_time_s: float | None) -> None:
        return None

    def on_session_end(self) -> None:
        self._tracker.reset()

    def snapshot(self) -> dict[str, Any]:
        snap = self._tracker.snapshot()
        rows = snap.get("rows", {}) or {}
        flags = snap.get("flags", []) or []
        return {
            "rows": rows,
            "flags": list(flags),
            "smoothness": _compute_smoothness(rows),
        }


def _compute_smoothness(rows: dict[str, Any]) -> float:
    """Derive a 0-1 smoothness score from brake + throttle diagnostics."""
    brake_score = (rows.get("brake_trace") or {}).get("score")
    throttle_score = (rows.get("throttle_modulation") or {}).get("score")
    scores = [s for s in (brake_score, throttle_score) if isinstance(s, (int, float))]
    if not scores:
        return _DEFAULT_SMOOTHNESS
    return max(0.0, min(1.0, sum(scores) / len(scores) / 100.0))


__all__ = ["InputDiagnosticsProcessor"]
