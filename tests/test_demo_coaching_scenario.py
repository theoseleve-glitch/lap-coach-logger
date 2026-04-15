"""Tests for demo coaching scenario."""
from __future__ import annotations

from lap_coach_logger.demo.coaching_scenario import (
    COACHING_ARC,
    ScriptedMoment,
    moment_for_lap,
)


def test_arc_has_four_moments():
    assert len(COACHING_ARC) >= 4


def test_moments_in_order():
    laps = [m.after_lap for m in COACHING_ARC]
    assert laps == sorted(laps)


def test_moment_for_lap_lookup():
    m = moment_for_lap(5)
    assert m is not None
    assert "plan" in m.title.lower()


def test_moment_for_unused_lap_returns_none():
    assert moment_for_lap(999) is None


def test_readiness_moment_at_end():
    m = moment_for_lap(10)
    assert m is not None
    assert "ready" in m.title.lower()
