"""Tests for practice_readiness module."""

from __future__ import annotations

import pytest

from lap_coach_logger.core.practice_readiness import (
    InputCorrelation,
    compute_nudges,
    compute_race_statistics,
    compute_readiness,
    correlate_inputs_consumption,
)
from lap_coach_logger.core.stint_store import CompoundProfile
from lap_coach_logger.core.strategy_models import PitProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(
    compound: str = "Soft",
    total_laps: int = 50,
    stint_count: int = 5,
    confidence: str = "high",
    thermal: dict | None = None,
    warmup: dict | None = None,
    degradation: dict | None = None,
    avg_lap_time_s: float = 92.0,
) -> CompoundProfile:
    return CompoundProfile(
        compound=compound,
        fuel_per_lap=2.5,
        fuel_curve=[2.5, 2.5],
        wear_per_lap=1.8,
        estimated_life=33,
        avg_lap_time_s=avg_lap_time_s,
        lap_time_delta_s=0.3,
        avg_track_temp_c=35.0,
        total_laps_logged=total_laps,
        stint_count=stint_count,
        confidence=confidence,
        thermal=thermal,
        warmup=warmup,
        degradation=degradation,
    )


def _make_pit_profile(
    beta_transit: float | None = 22.0,
    beta_fuel_rate: float | None = 0.4,
) -> PitProfile:
    return PitProfile(
        track="monza",
        beta_transit=beta_transit,
        beta_fuel_rate=beta_fuel_rate,
        beta_tire_change=3.0,
        r_squared=0.95,
        measurements=[],
    )


# ---------------------------------------------------------------------------
# TestComputeReadiness
# ---------------------------------------------------------------------------

class TestComputeReadiness:
    def test_fully_ready_compound(self):
        profiles = {
            "Soft": _make_profile(
                thermal={"available": True, "optimal_temp_low": 80},
                warmup={"fitted": True, "amplitude_s": 1.0},
                degradation={"available": True, "deg_rate_per_lap": 0.002},
                confidence="high",
                total_laps=50,
            ),
        }
        result = compute_readiness(profiles, None)

        assert result["Soft"]["readiness_pct"] == 100
        assert result["Soft"]["thermal"] is True
        assert result["Soft"]["warmup"] is True
        assert result["Soft"]["degradation"] is True
        assert result["Soft"]["confidence"] == "high"
        assert result["Soft"]["laps_needed_for_high"] == 0

    def test_no_data(self):
        result = compute_readiness({}, None)
        assert result == {}

    def test_partial_readiness(self):
        profiles = {
            "Hard": _make_profile(
                compound="Hard",
                total_laps=5,
                stint_count=1,
                confidence="low",
                thermal=None,
                warmup=None,
                degradation=None,
            ),
        }
        result = compute_readiness(profiles, None)

        assert result["Hard"]["readiness_pct"] == 0
        assert result["Hard"]["thermal"] is False
        assert result["Hard"]["warmup"] is False
        assert result["Hard"]["degradation"] is False
        assert result["Hard"]["confidence"] == "low"
        assert result["Hard"]["laps_needed_for_high"] == 25
        assert result["Hard"]["stints_needed_for_warmup"] == 2


# ---------------------------------------------------------------------------
# TestComputeNudges
# ---------------------------------------------------------------------------

class TestComputeNudges:
    def test_nudges_for_missing_data(self):
        profiles = {
            "Soft": _make_profile(
                total_laps=5,
                stint_count=1,
                confidence="low",
                thermal=None,
                warmup=None,
                degradation=None,
            ),
        }
        nudges = compute_nudges(profiles, _make_pit_profile(), ["Soft", "Hard"])

        # Should nudge to run laps on Hard (no data)
        assert any("Hard" in n for n in nudges)
        # Should nudge about low confidence on Soft
        assert any("confidence" in n.lower() for n in nudges)
        # Max 5
        assert len(nudges) <= 5

    def test_nudge_for_missing_pit(self):
        profiles = {
            "Soft": _make_profile(
                thermal={"available": True},
                warmup={"fitted": True},
                degradation={"available": True},
            ),
        }
        nudges = compute_nudges(profiles, None, ["Soft"])

        assert any("pit stop" in n.lower() for n in nudges)

    def test_race_ready_nudge(self):
        profiles = {
            "Soft": _make_profile(
                thermal={"available": True},
                warmup={"fitted": True},
                degradation={"available": True},
                confidence="high",
                total_laps=50,
                stint_count=5,
            ),
        }
        nudges = compute_nudges(profiles, _make_pit_profile(), ["Soft"])

        assert nudges == ["You're race-ready! Head to Build Strategy"]


# ---------------------------------------------------------------------------
# TestInputCorrelation
# ---------------------------------------------------------------------------

class TestInputCorrelation:
    def test_correlates_throttle_with_fuel(self):
        input_metrics = [
            {"throttle_aggressiveness": 0.9, "brake_intensity": 0.5},
            {"throttle_aggressiveness": 0.7, "brake_intensity": 0.4},
            {"throttle_aggressiveness": 0.5, "brake_intensity": 0.3},
        ]
        # Lap 2 (idx 2) is most efficient
        fuel_deltas = [3.0, 2.8, 2.5]
        wear_rates = [2.0, 1.8, 1.5]

        result = correlate_inputs_consumption(input_metrics, fuel_deltas, wear_rates)

        assert len(result) == 2  # two input keys
        assert all(isinstance(r, InputCorrelation) for r in result)
        # fuel_impact should be positive (average is worse than baseline)
        throttle = next(r for r in result if r.input_name == "throttle_aggressiveness")
        assert throttle.fuel_impact_l > 0

    def test_empty_returns_empty(self):
        result = correlate_inputs_consumption([], [], [])
        assert result == []

    def test_too_few_laps(self):
        result = correlate_inputs_consumption(
            [{"throttle": 0.5}],
            [2.5],
            [1.5],
        )
        assert result == []


# ---------------------------------------------------------------------------
# TestRaceStatistics
# ---------------------------------------------------------------------------

class TestRaceStatistics:
    def test_computes_basic_stats(self):
        profiles = {
            "Soft": _make_profile(avg_lap_time_s=90.0),
            "Hard": _make_profile(compound="Hard", avg_lap_time_s=92.0),
        }
        stints = [
            {
                "compound": "Soft",
                "start_lap": 0,
                "end_lap": 15,
                "stint_time_s": 1350.0,
                "grip_at_end": 72.0,
            },
            {
                "compound": "Hard",
                "start_lap": 15,
                "end_lap": 30,
                "stint_time_s": 1380.0,
                "grip_at_end": 65.0,
            },
        ]
        total_race_time_s = 2800.0
        fuel_at_finish = 1.5

        result = compute_race_statistics(
            stints, profiles, fuel_capacity=120.0,
            total_race_time_s=total_race_time_s,
            fuel_at_finish=fuel_at_finish,
        )

        assert result["estimated_laps"] == 30
        assert result["pit_stops"] == 1
        assert result["qualifying_target_s"] == 90.0
        assert result["estimated_race_time_s"] == 2800.0
        assert result["best_case_time_s"] == pytest.approx(2800.0 * 0.97)
        assert result["worst_case_time_s"] == pytest.approx(2800.0 * 1.05)
        assert result["fuel_margin_l"] == 1.5
        assert result["grip_at_finish_pct"] == 65.0
        # race_pace_target_s = (1350 + 1380) / 30 = 91.0
        assert result["race_pace_target_s"] == pytest.approx(91.0)

    def test_empty_stints(self):
        result = compute_race_statistics([], {}, 120.0, 0.0, 0.0)
        assert result == {}
