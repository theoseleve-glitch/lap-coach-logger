"""Tests for LIVE_COACHING_ENABLED feature flag (sprint T007).

When the ``LIVE_COACHING_ENABLED`` env var evaluates to false, the
CoachingLiveProcessor must no-op: no detector notes, no coaching
cards — even when samples would normally produce output. Default
(unset/true) preserves existing behavior.
"""
from __future__ import annotations

import pytest

from lap_coach_logger.core.coaching_live_processor import CoachingLiveProcessor
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


@pytest.mark.parametrize("value", ["0", "false", "False", "no", "off", "FALSE"])
def test_flag_disabled_produces_empty_snapshot(monkeypatch, value: str) -> None:
    monkeypatch.setenv("LIVE_COACHING_ENABLED", value)
    proc = CoachingLiveProcessor()
    for i in range(10):
        proc.on_sample(_sample(session_time_s=float(i)))
    snap = proc.snapshot()
    assert snap["cards"] == []
    assert snap["notes"] == []
    assert proc.enabled is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_flag_enabled_preserves_default_behavior(monkeypatch, value: str) -> None:
    monkeypatch.setenv("LIVE_COACHING_ENABLED", value)
    proc = CoachingLiveProcessor()
    proc.on_sample(_sample())
    snap = proc.snapshot()
    assert "cards" in snap
    assert "notes" in snap
    assert proc.enabled is True


def test_unset_defaults_to_enabled(monkeypatch) -> None:
    monkeypatch.delenv("LIVE_COACHING_ENABLED", raising=False)
    proc = CoachingLiveProcessor()
    assert proc.enabled is True
