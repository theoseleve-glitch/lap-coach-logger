"""Tests for DashboardLiveProcessor (sprint T004).

Exposes a normalized snapshot consumable by OverlayViewModel.
Composes LiveLapComparisonTracker + LiveCornerTracker +
TireDegradationTracker primitives behind the LiveProcessor ABC.
"""
from __future__ import annotations

from lap_coach_logger.core.dashboard_live_processor import DashboardLiveProcessor
from lap_coach_logger.core.live_processor import LiveProcessor
from lap_coach_logger.core.schema import TelemetrySample


def _sample(**kw) -> TelemetrySample:
    base = dict(
        sim="iracing",
        session_uid="s1",
        session_time_s=1.0,
        lap_number=1,
        lap_dist_pct=0.1,
        speed_kph=120.0,
        throttle_pct=0.5,
        brake_pct=0.0,
        steering_deg=0.0,
        long_accel_g=0.0,
        lat_accel_g=0.0,
    )
    base.update(kw)
    return TelemetrySample(**base)


def test_implements_live_processor_abc() -> None:
    proc = DashboardLiveProcessor()
    assert isinstance(proc, LiveProcessor)


def test_snapshot_has_normalized_keys() -> None:
    proc = DashboardLiveProcessor()
    proc.on_sample(_sample())
    snap = proc.snapshot()

    # Contract the VM relies on (mirrors current overlay_vm consumption).
    for key in (
        "live_delta_s",
        "best_lap_time_s",
        "last_lap_time_s",
        "current_lap_time_s",
        "best_lap_time_fmt",
        "last_lap_time_fmt",
        "current_lap_time_fmt",
        "sector_rows",
        "corner_rows",
        "tire_state",
    ):
        assert key in snap, f"missing dashboard key: {key}"

    assert isinstance(snap["sector_rows"], list)
    assert isinstance(snap["corner_rows"], list)
    assert isinstance(snap["tire_state"], dict)


def test_on_sample_accepts_dashboard_and_derived_state() -> None:
    proc = DashboardLiveProcessor()
    live = {"lap_number": 1, "lap_dist_pct": 0.1, "session_time_s": 1.0}
    proc.on_sample(_sample(), dashboard_state=live, derived_state={})
    snap = proc.snapshot()
    assert snap["live_delta_s"] == 0.0 or isinstance(snap["live_delta_s"], float)


def test_tire_state_populates_with_tyre_temps() -> None:
    proc = DashboardLiveProcessor()
    live = {
        "lap_number": 1,
        "tyre_temp_lf": 85.0,
        "tyre_temp_rf": 85.0,
        "tyre_temp_lr": 85.0,
        "tyre_temp_rr": 85.0,
    }
    proc.on_sample(_sample(), dashboard_state=live)
    snap = proc.snapshot()
    assert snap["tire_state"]  # non-empty after samples


def test_on_session_end_clears_lap_state() -> None:
    proc = DashboardLiveProcessor()
    proc.on_sample(_sample())
    proc.on_session_end()
    snap = proc.snapshot()
    # Post-reset, last/best/current lap times must be None (no completed laps).
    assert snap["best_lap_time_s"] is None
    assert snap["last_lap_time_s"] is None
    assert snap["live_delta_s"] == 0.0


def test_current_lap_time_fmt_is_string() -> None:
    proc = DashboardLiveProcessor()
    proc.on_sample(_sample())
    snap = proc.snapshot()
    assert isinstance(snap["current_lap_time_fmt"], str)
    assert isinstance(snap["best_lap_time_fmt"], str)
    assert isinstance(snap["last_lap_time_fmt"], str)
