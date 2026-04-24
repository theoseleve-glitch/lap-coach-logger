"""Tests for CoachingLiveProcessor (sprint T003).

Verifies the processor implements LiveProcessor, composes
``DetectorManager`` (from ``live_detectors``) and ``LiveCoachTracker``
primitives, and produces coaching notes / cards through its lifecycle.
"""
from __future__ import annotations

from lap_coach_logger.core.coaching_live_processor import CoachingLiveProcessor
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
        throttle_pct=0.0,
        brake_pct=0.9,
        steering_deg=0.0,
        long_accel_g=-1.1,
        lat_accel_g=0.1,
    )
    base.update(kw)
    return TelemetrySample(**base)


def test_implements_live_processor_abc() -> None:
    proc = CoachingLiveProcessor()
    assert isinstance(proc, LiveProcessor)


def test_on_sample_accepts_telemetry_sample() -> None:
    proc = CoachingLiveProcessor()
    # Should not raise and should consume multiple samples.
    for i in range(5):
        proc.on_sample(_sample(session_time_s=float(i), lap_dist_pct=0.1 + 0.01 * i))


def test_snapshot_returns_cards_list() -> None:
    proc = CoachingLiveProcessor()
    proc.on_sample(_sample())
    snap = proc.snapshot()
    assert "cards" in snap
    assert isinstance(snap["cards"], list)
    assert "notes" in snap
    assert isinstance(snap["notes"], list)


def test_on_lap_end_and_session_end_reset_state() -> None:
    proc = CoachingLiveProcessor()
    proc.on_sample(_sample())
    proc.on_lap_end(1, 90.0)
    proc.on_session_end()
    snap = proc.snapshot()
    assert snap["cards"] == []
    assert snap["notes"] == []


def test_uses_detector_manager_primitive() -> None:
    from lap_coach_logger.core.live_detectors import DetectorManager

    proc = CoachingLiveProcessor()
    assert isinstance(proc.detector_manager, DetectorManager)
