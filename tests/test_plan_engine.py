"""Tests for the coaching plan engine."""
from __future__ import annotations

import pytest

from lap_coach_logger.coaching.output import Confidence, CoachingOutput
from lap_coach_logger.coaching.plan_engine import CoachingPlan, generate_plan
from lap_coach_logger.coaching.plan_evaluator import PlanResult
from lap_coach_logger.core.consistency_analyzer import ConsistencyReport


def _make_report(**overrides) -> ConsistencyReport:
    """Build a ConsistencyReport with sensible defaults, overridable."""
    defaults = dict(
        overall_std_dev_s=0.5,
        consistency_pct=95.0,
        median_lap_time_s=90.0,
        best_lap_time_s=88.5,
        theoretical_best_s=87.0,
        per_sector_std_dev=[0.15, 0.35, 0.20],
        worst_sector=1,
        worst_corners=[
            {"name": "T5", "std_dev_s": 0.40},
            {"name": "T9", "std_dev_s": 0.25},
            {"name": "T1", "std_dev_s": 0.10},
        ],
        trend="stable",
        focus_recommendation="Focus on Sector 2",
        lap_count=10,
    )
    defaults.update(overrides)
    return ConsistencyReport(**defaults)


class TestGeneratePlan:
    """Plan engine tests."""

    def test_generates_plan_from_consistency_report(self):
        report = _make_report()
        output = generate_plan(report, laps_completed=10)

        assert isinstance(output, CoachingOutput)
        assert output.confidence in (Confidence.HIGH, Confidence.MEDIUM)
        plan: CoachingPlan = output.value
        assert plan is not None
        assert plan.focus_area  # non-empty
        assert plan.objective
        assert plan.measurable_target
        assert plan.evaluation_window == 5
        assert len(plan.ignore_list) > 0

    def test_focuses_on_worst_corner_when_significant(self):
        # T5 std_dev (0.40) > overall (0.5) * 0.5 = 0.25 => corner focus
        report = _make_report(
            overall_std_dev_s=0.5,
            worst_corners=[
                {"name": "T5", "std_dev_s": 0.40},
                {"name": "T9", "std_dev_s": 0.25},
            ],
        )
        output = generate_plan(report, laps_completed=10)
        plan: CoachingPlan = output.value

        assert plan.focus_area == "T5"
        assert "T5" in plan.measurable_target
        # Ignore list should exclude T5 but mention others
        assert any("T5" not in item for item in plan.ignore_list)

    def test_focuses_on_worst_sector_when_no_corners(self):
        report = _make_report(
            worst_corners=[],
            per_sector_std_dev=[0.10, 0.40, 0.15],
            overall_std_dev_s=0.5,
        )
        output = generate_plan(report, laps_completed=10)
        plan: CoachingPlan = output.value

        assert plan.focus_area == "Sector 2"
        assert "Sector 2" in plan.measurable_target

    def test_returns_low_confidence_with_insufficient_data(self):
        # None report
        output_none = generate_plan(None, laps_completed=2)
        assert output_none.confidence == Confidence.LOW
        assert output_none.value is None

        # Report with too few laps
        report = _make_report(lap_count=2)
        output_few = generate_plan(report, laps_completed=2)
        assert output_few.confidence == Confidence.LOW
        assert output_few.value is None

    def test_advances_focus_after_successful_plan(self):
        report = _make_report(
            worst_corners=[
                {"name": "T5", "std_dev_s": 0.40},
                {"name": "T9", "std_dev_s": 0.30},
            ],
        )
        # Simulate previous success on T5
        prev_result = PlanResult(
            success=True,
            delta_vs_target=-0.05,
            updated_std_dev=0.20,
            next_action="advance",
            confidence=Confidence.HIGH,
            reason="Focus area: T5",
        )
        output = generate_plan(report, laps_completed=15, previous_plan_result=prev_result)
        plan: CoachingPlan = output.value

        # Should NOT pick T5 again -- should advance to next worst
        assert plan.focus_area != "T5"

    def test_continues_focus_after_failed_plan(self):
        report = _make_report(
            worst_corners=[
                {"name": "T5", "std_dev_s": 0.40},
            ],
        )
        prev_result = PlanResult(
            success=False,
            delta_vs_target=0.10,
            updated_std_dev=0.45,
            next_action="continue",
            confidence=Confidence.LOW,
            reason="Reassess approach for T5",
        )
        output = generate_plan(report, laps_completed=15, previous_plan_result=prev_result)
        plan: CoachingPlan = output.value

        # Should still focus on T5 (failed plan => don't skip)
        assert plan.focus_area == "T5"
        # Target should be easier (0.85 factor vs 0.7)
        assert "\u00b1" in plan.measurable_target


# ---------------------------------------------------------------------------
# Corner-level technique coaching integration (sprint)
# ---------------------------------------------------------------------------

class TestCornerFocusedPlan:
    """Corner insights should upgrade the plan when they're significant."""

    def test_high_confidence_corner_takes_over_sector_focus(self):
        from lap_coach_logger.coaching.corner_insights import CornerInsight

        report = _make_report(
            overall_std_dev_s=0.15,  # low variance — normally no strong sector focus
            per_sector_std_dev=[0.1, 0.15, 0.1],
            worst_corners=[],
            lap_count=10,
        )
        insights = [
            CornerInsight(
                corner_name="T7",
                time_loss_s=0.45,     # big loss dominates the 0.15s std
                exit_speed_delta_kph=-6.0,
                throttle_pickup_delta_pct=0.01,
                loss_zone="exit",
                confidence="high",
            ),
            CornerInsight(
                corner_name="T1",
                time_loss_s=0.04,     # below noise floor
                confidence="high",
            ),
        ]
        output = generate_plan(report, laps_completed=10, corner_insights=insights)
        plan: CoachingPlan = output.value

        assert plan is not None
        assert plan.focus_area == "T7"
        assert plan.corner_focus == "T7"
        assert plan.technique_action  # non-empty
        assert plan.likely_cause
        assert "T7" in plan.measurable_target
        assert plan.confidence == Confidence.HIGH

    def test_low_confidence_corner_falls_back_to_sector_focus(self):
        from lap_coach_logger.coaching.corner_insights import CornerInsight

        report = _make_report(
            overall_std_dev_s=0.5,
            per_sector_std_dev=[0.1, 0.45, 0.1],
            worst_corners=[],
        )
        insights = [
            CornerInsight(
                corner_name="T7",
                time_loss_s=0.45,
                confidence="low",  # not trustworthy
            ),
        ]
        output = generate_plan(report, laps_completed=10, corner_insights=insights)
        plan: CoachingPlan = output.value

        # Falls back to sector-level focus
        assert plan is not None
        assert plan.corner_focus == ""  # no corner takeover
        assert plan.focus_area.startswith("Sector")

    def test_small_corner_loss_does_not_override_sector(self):
        from lap_coach_logger.coaching.corner_insights import CornerInsight

        report = _make_report(
            overall_std_dev_s=0.5,
            per_sector_std_dev=[0.1, 0.45, 0.1],
            worst_corners=[],
        )
        insights = [
            CornerInsight(
                corner_name="T7",
                time_loss_s=0.10,  # below 0.15s floor
                confidence="high",
            ),
        ]
        output = generate_plan(report, laps_completed=10, corner_insights=insights)
        plan: CoachingPlan = output.value

        # Small corner loss doesn't dominate — stay sector-focused
        assert plan.corner_focus == ""
        assert plan.focus_area.startswith("Sector")

    def test_corner_focus_requires_loss_to_dominate_variance(self):
        from lap_coach_logger.coaching.corner_insights import CornerInsight

        # Loss exists but overall variance is massive → inconsistency wins
        report = _make_report(
            overall_std_dev_s=1.5,
            per_sector_std_dev=[0.5, 1.0, 0.5],
            worst_corners=[],
        )
        insights = [
            CornerInsight(
                corner_name="T7",
                time_loss_s=0.20,  # not >= 1.5 * 1.5s
                confidence="high",
            ),
        ]
        output = generate_plan(report, laps_completed=10, corner_insights=insights)
        plan: CoachingPlan = output.value

        assert plan.corner_focus == ""  # inconsistency too broad
