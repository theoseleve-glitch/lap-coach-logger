"""Tests for readiness blocker-type classifier (Part 4)."""
from __future__ import annotations

import pytest

from lap_coach_logger.coaching.corner_insights import CornerInsight
from lap_coach_logger.core.practice_readiness import (
    ReadinessAction,
    classify_readiness_blocker,
    compute_readiness_action,
)


def _insight(name: str, loss: float, zone: str = "even") -> CornerInsight:
    return CornerInsight(
        corner_name=name,
        time_loss_s=loss,
        loss_zone=zone,
        confidence="medium",
    )


class TestClassifyReadinessBlocker:
    def test_no_insights_with_low_std_returns_none(self):
        blocker = classify_readiness_blocker(
            corner_insights_history=[], consistency_std=0.4,
        )
        assert blocker == "none"

    def test_no_insights_with_high_std_returns_broad_inconsistency(self):
        blocker = classify_readiness_blocker(
            corner_insights_history=[], consistency_std=1.5,
        )
        assert blocker == "broad_inconsistency"

    def test_one_major_corner_dominates(self):
        history = [
            [_insight("T5", 0.6, zone="exit"), _insight("T1", 0.05)],
            [_insight("T5", 0.5, zone="exit"), _insight("T1", 0.03)],
            [_insight("T5", 0.4, zone="exit")],
        ]
        blocker = classify_readiness_blocker(
            corner_insights_history=history, consistency_std=0.5,
        )
        assert blocker == "one_major_corner"

    def test_repeated_exit_issues_across_multiple_corners(self):
        history = [
            [
                _insight("T5", 0.15, zone="exit"),
                _insight("T7", 0.15, zone="exit"),
                _insight("T9", 0.15, zone="exit"),
            ],
            [
                _insight("T5", 0.12, zone="exit"),
                _insight("T7", 0.11, zone="exit"),
                _insight("T9", 0.10, zone="exit"),
            ],
        ]
        blocker = classify_readiness_blocker(
            corner_insights_history=history, consistency_std=0.4,
        )
        assert blocker == "repeated_exit_issue"

    def test_repeated_braking_issues_across_multiple_corners(self):
        history = [
            [
                _insight("T5", 0.15, zone="entry"),
                _insight("T7", 0.14, zone="entry"),
                _insight("T9", 0.12, zone="entry"),
            ],
        ]
        blocker = classify_readiness_blocker(
            corner_insights_history=history, consistency_std=0.4,
        )
        assert blocker == "repeated_braking_issue"

    def test_broad_inconsistency_when_many_small_losses(self):
        # 5 corners each contributing small loss, no single zone dominates
        history = [
            [
                _insight("T1", 0.12, zone="mid"),
                _insight("T3", 0.10, zone="entry"),
                _insight("T5", 0.08, zone="exit"),
                _insight("T7", 0.09, zone="mid"),
            ],
        ]
        blocker = classify_readiness_blocker(
            corner_insights_history=history, consistency_std=0.9,
        )
        # Consistency > 0.8 wins, or broad_inconsistency via many-corner rule
        assert blocker in ("broad_inconsistency", "repeated_braking_issue")


class TestComputeReadinessActionWithBlocker:
    def test_blocker_drives_action_when_building(self):
        history = [
            [_insight("T5", 0.5, zone="exit")],
            [_insight("T5", 0.4, zone="exit")],
            [_insight("T5", 0.3, zone="exit")],
        ]
        action = compute_readiness_action(
            profiles={},
            pit_profile=None,
            lap_count=10,
            consistency_std=0.6,
            corner_insights_history=history,
        )
        assert isinstance(action, ReadinessAction)
        assert action.blocker_type == "one_major_corner"
        # Suggested action should name the corner, not a generic model hint
        assert "T5" in action.suggested_action

    def test_no_blocker_falls_back_to_generic_action(self):
        action = compute_readiness_action(
            profiles={}, pit_profile=None, lap_count=10,
            consistency_std=0.3,
            corner_insights_history=None,
        )
        assert action.blocker_type == "none"
        # Should mention missing models rather than a corner
        assert "T5" not in action.suggested_action

    def test_state_not_ready_when_few_laps(self):
        action = compute_readiness_action(
            profiles={}, pit_profile=None, lap_count=2,
            consistency_std=None,
        )
        assert action.state == "not_ready"
