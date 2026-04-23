"""Tests for the post-session strategy review model."""
from __future__ import annotations

import pytest

from lap_coach_logger.coaching.strategy_review import (
    DIVERGENCE_EARLY_STOP,
    DIVERGENCE_EXTRA_STOP,
    DIVERGENCE_LATE_STOP,
    DIVERGENCE_NONE,
    DIVERGENCE_OVER_FUELED,
    DIVERGENCE_SKIPPED_STOP,
    DIVERGENCE_UNDER_FUELED,
    StrategyReview,
    VERDICT_ADJUSTED,
    VERDICT_DIVERGED,
    VERDICT_INSUFFICIENT,
    VERDICT_NO_PLAN,
    VERDICT_ON_PLAN,
    build_strategy_review,
    review_to_dict,
)
from lap_coach_logger.core.race_strategy import PlannedStint, RacePlan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(pit_laps: list[int], fuel_to_add: list[float]) -> RacePlan:
    """Build a RacePlan with (N+1) stints from N planned pit laps."""
    if len(pit_laps) + 1 != len(fuel_to_add) + 1:
        # fuel_to_add includes each stint's starting fuel; use a simpler signature:
        pass
    stints: list[PlannedStint] = []
    prev_end = 0
    # First stint starts at lap 1
    starts = [1] + [l + 1 for l in pit_laps]
    ends = pit_laps + [starts[-1] + 20]  # last stint ends arbitrarily 20 laps after
    for idx, (start, end) in enumerate(zip(starts, ends)):
        stints.append(PlannedStint(
            compound="soft",
            start_lap=start,
            end_lap=end,
            fuel_at_start=60.0,
            fuel_to_add=fuel_to_add[idx] if idx < len(fuel_to_add) else 0.0,
            grip_at_end=60.0,
            estimated_time_s=1500.0,
        ))
    return RacePlan(
        stints=stints,
        total_race_time_s=3000.0,
        fuel_at_finish=2.0,
        alerts=[],
    )


# ---------------------------------------------------------------------------
# Empty / degraded cases
# ---------------------------------------------------------------------------

class TestDegradedCases:
    def test_no_plan_returns_no_plan_verdict(self):
        review = build_strategy_review(
            original_plan=None,
            actual_pit_laps=[],
            actual_fuel_added=[],
        )
        assert review.verdict == VERDICT_NO_PLAN
        assert review.degraded is True
        assert "No plan" in review.rows[0]

    def test_plan_with_no_stints_returns_no_plan(self):
        empty_plan = RacePlan(stints=[], total_race_time_s=0.0, fuel_at_finish=0.0, alerts=[])
        review = build_strategy_review(
            original_plan=empty_plan,
            actual_pit_laps=[],
            actual_fuel_added=[],
        )
        assert review.verdict == VERDICT_NO_PLAN

    def test_race_never_started_returns_insufficient(self):
        plan = _make_plan(pit_laps=[20], fuel_to_add=[0.0, 40.0])
        review = build_strategy_review(
            original_plan=plan,
            actual_pit_laps=[],
            actual_fuel_added=[],
            final_fuel_l=0.0,
        )
        assert review.verdict == VERDICT_INSUFFICIENT
        assert review.degraded is True


# ---------------------------------------------------------------------------
# Exact-plan matches
# ---------------------------------------------------------------------------

class TestOnPlan:
    def test_exact_plan_match_returns_on_plan(self):
        plan = _make_plan(pit_laps=[20], fuel_to_add=[0.0, 40.0])
        review = build_strategy_review(
            original_plan=plan,
            actual_pit_laps=[20],
            actual_fuel_added=[40.0],
            final_fuel_l=2.0,
        )
        assert review.verdict == VERDICT_ON_PLAN
        assert review.biggest_divergence == DIVERGENCE_NONE
        assert review.planned_stops == 1
        assert review.actual_stops == 1
        assert not review.degraded

    def test_within_lap_tolerance_still_on_plan(self):
        plan = _make_plan(pit_laps=[20], fuel_to_add=[0.0, 40.0])
        review = build_strategy_review(
            original_plan=plan,
            actual_pit_laps=[21],   # 1 lap late — within tolerance
            actual_fuel_added=[40.0],
            final_fuel_l=2.0,
        )
        assert review.verdict == VERDICT_ON_PLAN
        assert review.biggest_divergence == DIVERGENCE_NONE


# ---------------------------------------------------------------------------
# Stop-count divergences
# ---------------------------------------------------------------------------

class TestStopCountDivergence:
    def test_extra_stop_is_flagged_as_diverged(self):
        plan = _make_plan(pit_laps=[20], fuel_to_add=[0.0, 40.0])
        review = build_strategy_review(
            original_plan=plan,
            actual_pit_laps=[15, 30],   # unplanned extra stop
            actual_fuel_added=[20.0, 25.0],
            final_fuel_l=2.0,
        )
        assert review.verdict == VERDICT_DIVERGED
        assert review.biggest_divergence == DIVERGENCE_EXTRA_STOP
        assert review.actual_stops == 2

    def test_skipped_stop_is_flagged(self):
        plan = _make_plan(pit_laps=[15, 30], fuel_to_add=[0.0, 30.0, 30.0])
        review = build_strategy_review(
            original_plan=plan,
            actual_pit_laps=[15],   # one missed
            actual_fuel_added=[40.0],
            final_fuel_l=2.0,
        )
        assert review.verdict == VERDICT_DIVERGED
        assert review.biggest_divergence == DIVERGENCE_SKIPPED_STOP


# ---------------------------------------------------------------------------
# Timing divergences
# ---------------------------------------------------------------------------

class TestTimingDivergence:
    def test_early_stop_by_3_laps_is_flagged(self):
        plan = _make_plan(pit_laps=[20], fuel_to_add=[0.0, 40.0])
        review = build_strategy_review(
            original_plan=plan,
            actual_pit_laps=[17],  # 3 laps early
            actual_fuel_added=[40.0],
            final_fuel_l=2.0,
        )
        assert review.biggest_divergence == DIVERGENCE_EARLY_STOP
        assert "3 laps" in review.biggest_divergence_detail

    def test_late_stop_by_4_laps_is_flagged(self):
        plan = _make_plan(pit_laps=[20], fuel_to_add=[0.0, 40.0])
        review = build_strategy_review(
            original_plan=plan,
            actual_pit_laps=[24],
            actual_fuel_added=[40.0],
            final_fuel_l=2.0,
        )
        assert review.biggest_divergence == DIVERGENCE_LATE_STOP


# ---------------------------------------------------------------------------
# Fuel divergence
# ---------------------------------------------------------------------------

class TestFuelDivergence:
    def test_small_fuel_variance_is_adjusted_not_diverged(self):
        plan = _make_plan(pit_laps=[20], fuel_to_add=[0.0, 40.0])
        review = build_strategy_review(
            original_plan=plan,
            actual_pit_laps=[20],
            actual_fuel_added=[43.0],   # +3L — above 2L tolerance, still within 4L
            final_fuel_l=2.0,
        )
        assert review.biggest_divergence == DIVERGENCE_OVER_FUELED
        # Verdict is "adjusted" because variance ≤ 2× tolerance
        assert review.verdict == VERDICT_ADJUSTED

    def test_big_under_fuel_is_diverged(self):
        plan = _make_plan(pit_laps=[20], fuel_to_add=[0.0, 40.0])
        review = build_strategy_review(
            original_plan=plan,
            actual_pit_laps=[20],
            actual_fuel_added=[30.0],  # 10L under
            final_fuel_l=2.0,
        )
        assert review.biggest_divergence == DIVERGENCE_UNDER_FUELED
        assert review.verdict == VERDICT_DIVERGED
        assert review.fuel_variance_l == pytest.approx(-10.0)


# ---------------------------------------------------------------------------
# Presentation rows + next-time suggestion
# ---------------------------------------------------------------------------

class TestPresentation:
    def test_rows_are_capped_at_five(self):
        plan = _make_plan(pit_laps=[15, 30], fuel_to_add=[0.0, 30.0, 30.0])
        review = build_strategy_review(
            original_plan=plan,
            actual_pit_laps=[15, 30],
            actual_fuel_added=[30.0, 30.0],
            final_fuel_l=2.0,
        )
        assert len(review.rows) <= 5

    def test_next_time_suggestion_is_non_empty_for_any_verdict(self):
        plan = _make_plan(pit_laps=[20], fuel_to_add=[0.0, 40.0])
        review = build_strategy_review(
            original_plan=plan,
            actual_pit_laps=[25],
            actual_fuel_added=[40.0],
            final_fuel_l=2.0,
        )
        assert review.next_time_suggestion

    def test_review_to_dict_has_stable_shape(self):
        review = StrategyReview(
            verdict=VERDICT_ON_PLAN,
            planned_stops=1,
            actual_stops=1,
            fuel_variance_l=0.0,
            rows=("ok",),
            degraded=False,
        )
        d = review_to_dict(review)
        assert set(d.keys()) == {
            "verdict", "planned_stops", "actual_stops",
            "biggest_divergence", "biggest_divergence_detail",
            "fuel_variance_l", "next_time_suggestion",
            "rows", "degraded",
        }
