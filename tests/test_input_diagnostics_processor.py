"""Tests for InputDiagnosticsProcessor (sprint T005).

Wraps LiveInputDiagnosticsTracker behind the LiveProcessor ABC and
surfaces a compact snapshot (rows + flags + smoothness score) for
input-oriented overlay widgets (pedal trace, g-g, input linearity).
"""
from __future__ import annotations

from lap_coach_logger.core.input_diagnostics_processor import (
    InputDiagnosticsProcessor,
)
from lap_coach_logger.core.live_processor import LiveProcessor
from lap_coach_logger.core.schema import TelemetrySample


def _sample(**kw) -> TelemetrySample:
    base = dict(
        sim="iracing",
        session_uid="s1",
        session_time_s=1.0,
        lap_number=1,
        lap_dist_pct=0.1,
        speed_kph=80.0,
        throttle_pct=0.8,
        brake_pct=0.0,
        steering_deg=0.0,
    )
    base.update(kw)
    return TelemetrySample(**base)


def test_implements_live_processor_abc() -> None:
    proc = InputDiagnosticsProcessor()
    assert isinstance(proc, LiveProcessor)


def test_snapshot_exposes_rows_flags_and_smoothness() -> None:
    proc = InputDiagnosticsProcessor()
    for i in range(5):
        proc.on_sample(_sample(session_time_s=float(i)))
    snap = proc.snapshot()
    assert "rows" in snap
    assert isinstance(snap["rows"], dict)
    assert "flags" in snap
    assert isinstance(snap["flags"], list)
    assert "smoothness" in snap
    assert 0.0 <= snap["smoothness"] <= 1.0


def test_smoothness_defaults_before_enough_data() -> None:
    # No samples yet — smoothness returns a sensible default (0.75).
    proc = InputDiagnosticsProcessor()
    snap = proc.snapshot()
    assert snap["smoothness"] == 0.75


def test_on_session_end_resets_tracker() -> None:
    proc = InputDiagnosticsProcessor()
    proc.on_sample(_sample())
    proc.on_session_end()
    # After reset, default smoothness returns.
    snap = proc.snapshot()
    assert snap["smoothness"] == 0.75


def test_on_sample_forwards_dashboard_and_derived_state() -> None:
    proc = InputDiagnosticsProcessor()
    # Should not raise when dashboard/derived state provided.
    proc.on_sample(
        _sample(),
        dashboard_state={"ffb_clip_pct": 0.5},
        derived_state={"anything": 1},
    )
    snap = proc.snapshot()
    assert "rows" in snap
