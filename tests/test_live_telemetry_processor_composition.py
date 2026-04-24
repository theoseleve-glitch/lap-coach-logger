"""Tests for LiveTelemetryProcessor composition (sprint T006).

``LiveTelemetryProcessor`` composes ``CoachingLiveProcessor``,
``DashboardLiveProcessor``, and ``InputDiagnosticsProcessor`` — each
a concrete ``LiveProcessor`` — and aggregates their snapshots while
preserving the ``process()`` output contract the overlay VM relies on.
"""
from __future__ import annotations

from lap_coach_logger.core.coaching_live_processor import CoachingLiveProcessor
from lap_coach_logger.core.dashboard_live_processor import DashboardLiveProcessor
from lap_coach_logger.core.input_diagnostics_processor import (
    InputDiagnosticsProcessor,
)
from lap_coach_logger.core.live_processor import LiveProcessor
from lap_coach_logger.core.live_telemetry_processor import LiveTelemetryProcessor


def _live(**kw) -> dict:
    base = dict(
        session_uid="s1",
        session_time_s=1.0,
        lap_number=1,
        lap_dist_pct=0.1,
        speed_kph=120.0,
        throttle_pct=0.8,
        brake_pct=0.0,
        steering_deg=0.0,
        long_accel_g=0.0,
        lat_accel_g=0.0,
    )
    base.update(kw)
    return base


SNAP = {"sim": "iracing"}


def test_composes_three_subprocessors_via_abc() -> None:
    proc = LiveTelemetryProcessor()
    subs = [proc._coaching, proc._dashboard, proc._input]  # noqa: SLF001
    assert isinstance(proc._coaching, CoachingLiveProcessor)
    assert isinstance(proc._dashboard, DashboardLiveProcessor)
    assert isinstance(proc._input, InputDiagnosticsProcessor)
    for sub in subs:
        assert isinstance(sub, LiveProcessor)


def test_process_keeps_vm_contract_keys() -> None:
    proc = LiveTelemetryProcessor()
    result = proc.process(_live(), SNAP)
    for key in (
        "live_delta_s",
        "best_lap_time_s",
        "last_lap_time_s",
        "current_lap_time_s",
        "best_lap_time_fmt",
        "last_lap_time_fmt",
        "current_lap_time_fmt",
        "sector_rows",
        "lockup_active",
        "wheelspin_active",
        "coaching_cards",
        "input_smoothness",
        "corner_rows",
        "tire_state",
        "corner_insights",
        "corner_insights_lap",
    ):
        assert key in result, f"missing contract key: {key}"

    assert isinstance(result["coaching_cards"], list)
    assert isinstance(result["sector_rows"], list)
    assert isinstance(result["corner_rows"], list)
    assert isinstance(result["tire_state"], dict)
    assert isinstance(result["live_delta_s"], float)
    assert isinstance(result["lockup_active"], bool)
    assert isinstance(result["wheelspin_active"], bool)


def test_process_detects_lockup_on_raw_sample() -> None:
    proc = LiveTelemetryProcessor()
    # Heavy braking + speed + deceleration → lockup_active true.
    live = _live(brake_pct=0.9, speed_kph=200.0, long_accel_g=-1.5)
    result = proc.process(live, SNAP)
    assert result["lockup_active"] is True


def test_reset_clears_sub_processor_state() -> None:
    proc = LiveTelemetryProcessor()
    proc.process(_live(), SNAP)
    proc.reset()
    result = proc.process(_live(), SNAP)
    # After reset, corner insights start empty again.
    assert result["corner_insights"] == []
    assert result["corner_insights_lap"] is None


def test_input_smoothness_is_bounded() -> None:
    proc = LiveTelemetryProcessor()
    for i in range(5):
        proc.process(_live(session_time_s=float(i), lap_dist_pct=0.1 + 0.01 * i), SNAP)
    result = proc.process(_live(session_time_s=6.0), SNAP)
    assert 0.0 <= result["input_smoothness"] <= 1.0
