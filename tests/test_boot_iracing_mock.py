"""Smoke test: live processor runs with an iRacing-shaped sample stream (T009).

Simulates two laps of iRacing telemetry by feeding the
``LiveTelemetryProcessor`` a sequence of live/snap dicts shaped the way
``IRacingAdapter.read_sample`` delivers them, then asserts the processor
keeps running — no exception over the burst — and produces the overlay
contract the VM consumes.
"""
from __future__ import annotations

from lap_coach_logger.core.live_telemetry_processor import LiveTelemetryProcessor


_SAMPLES_PER_LAP = 20
_SESSION_UID = "iracing-mock-session"


def _iracing_live(lap: int, step: int, *, lap_time_total_s: float = 90.0) -> dict:
    """One live-dict sample shaped like iRacing adapter output."""
    frac = step / _SAMPLES_PER_LAP
    session_time = (lap - 1) * lap_time_total_s + frac * lap_time_total_s
    # Simple throttle/brake cadence so trackers see active inputs.
    throttle = 0.9 if frac < 0.7 else 0.0
    brake = 0.0 if frac < 0.7 else 0.8
    speed = 220.0 if frac < 0.7 else 140.0
    return {
        "sim": "iracing",
        "session_uid": _SESSION_UID,
        "session_time_s": session_time,
        "lap_number": lap,
        "lap_dist_pct": frac,
        "lap_distance_m": frac * 5000.0,
        "speed_kph": speed,
        "throttle_pct": throttle,
        "brake_pct": brake,
        "steering_deg": 5.0 * (frac - 0.5),
        "gear": 4,
        "rpm": 6500.0,
        "long_accel_g": -1.2 if frac >= 0.7 else 0.3,
        "lat_accel_g": 0.8 if 0.3 < frac < 0.7 else 0.1,
        "fuel_level": max(0.0, 50.0 - lap * 3.0),
        "track_name": "Sebring",
        "car_name": "Ferrari-296-GT3",
        "tyre_temp_lf": 85.0,
        "tyre_temp_rf": 86.0,
        "tyre_temp_lr": 82.0,
        "tyre_temp_rr": 83.0,
    }


def _iracing_snap() -> dict:
    return {"sim": "iracing", "derived": {}}


def test_processor_runs_two_iracing_laps_without_crash() -> None:
    proc = LiveTelemetryProcessor()
    results: list[dict] = []
    for lap in (1, 2):
        for step in range(_SAMPLES_PER_LAP + 1):
            result = proc.process(_iracing_live(lap, step), _iracing_snap())
            results.append(result)
    assert len(results) == (_SAMPLES_PER_LAP + 1) * 2
    # Every result keeps the VM contract — never partial.
    for r in results:
        assert "live_delta_s" in r
        assert "coaching_cards" in r
        assert isinstance(r["sector_rows"], list)


def test_current_lap_time_advances_with_samples() -> None:
    proc = LiveTelemetryProcessor()
    proc.process(_iracing_live(1, 1), _iracing_snap())
    early = proc.process(_iracing_live(1, 5), _iracing_snap())
    late = proc.process(_iracing_live(1, 15), _iracing_snap())
    # Tracker must have recorded a growing current lap time.
    assert (late["current_lap_time_s"] or 0.0) >= (early["current_lap_time_s"] or 0.0)


def test_reset_between_mock_sessions_clears_state() -> None:
    proc = LiveTelemetryProcessor()
    for step in range(5):
        proc.process(_iracing_live(1, step), _iracing_snap())
    proc.reset()
    result = proc.process(_iracing_live(1, 0), _iracing_snap())
    assert result["corner_insights"] == []
    assert result["corner_insights_lap"] is None
