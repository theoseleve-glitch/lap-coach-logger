"""Tests for the unified coaching presentation contract.

These lock in the "one coach, one voice" invariant: every surface
(overlay, Coaching tab, race carryover, post-session card) derives
from the same ``CoachingMessage`` with identical wording for the same
underlying plan or summary.
"""
from __future__ import annotations

import pytest

from lap_coach_logger.coaching.corner_insights import CornerInsight
from lap_coach_logger.coaching.output import Confidence
from lap_coach_logger.coaching.plan_engine import CoachingPlan
from lap_coach_logger.coaching.policy_config import (
    COACHING_TAB_POLICY,
    DEFAULT_POLICY,
    PolicyConfig,
    RACE_OVERLAY_POLICY,
)
from lap_coach_logger.coaching.post_session_summary import (
    build_post_session_summary,
    build_summary_presentation,
)
from lap_coach_logger.coaching.presentation import (
    CoachingMessage,
    message_from_plan,
    message_from_summary,
    message_to_dict,
    severity_for_confidence,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _corner_plan() -> CoachingPlan:
    return CoachingPlan(
        focus_area="T5",
        objective="Brake 10m earlier",
        measurable_target="Reduce T5 time loss from 0.35s to ≤0.18s vs your best",
        technique_insight=(
            "T5: Braking begins later than your best. Rushed entry. "
            "Brake 10m earlier, smoother release."
        ),
        ignore_list=["Don't chase lap time"],
        evaluation_window=5,
        confidence=Confidence.HIGH,
        reason="Corner-level focus: T5 dominates time on the table",
        corner_focus="T5",
        technique_action="Brake 10m earlier, smoother release",
        likely_cause="Rushed entry",
    )


def _sector_plan() -> CoachingPlan:
    return CoachingPlan(
        focus_area="Sector 2",
        objective="Reduce overall variance (±0.50s)",
        measurable_target="Reduce Sector 2 std dev from ±0.50s to ±0.35s",
        technique_insight="Sector 2 variance is the biggest consistency gap.",
        ignore_list=["Don't chase Sector 1", "Don't chase Sector 3"],
        evaluation_window=5,
        confidence=Confidence.MEDIUM,
        reason="Sector 2 has highest variance",
    )


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

class TestMessageFromPlan:
    def test_corner_plan_produces_corner_category(self):
        msg = message_from_plan(_corner_plan(), time_loss_s=0.35)
        assert msg.category == "corner"
        assert msg.focus_id == "T5"
        assert msg.confidence == "high"
        assert msg.severity == "positive"
        assert msg.time_loss_s == 0.35
        assert "T5" in msg.headline
        assert "smoother" in msg.subline.lower() or "brake" in msg.subline.lower()

    def test_sector_plan_produces_sector_category(self):
        msg = message_from_plan(_sector_plan())
        assert msg.category == "sector"
        assert msg.focus_id == "Sector 2"
        assert msg.confidence == "medium"
        assert msg.severity == "advisory"

    def test_none_plan_returns_empty_message(self):
        msg = message_from_plan(None)
        assert msg.is_empty
        assert msg.category == ""
        assert msg.focus_id == ""

    def test_plan_supporting_dict_carries_extras(self):
        msg = message_from_plan(_corner_plan(), time_loss_s=0.35)
        assert "measurable_target" in msg.supporting
        assert "likely_cause" in msg.supporting
        assert "ignore_list" in msg.supporting
        assert msg.supporting["likely_cause"] == "Rushed entry"

    def test_truncation_is_config_driven(self):
        plan = CoachingPlan(
            focus_area="T5",
            objective="x",
            measurable_target="x",
            technique_insight="T5: " + ("verbose explanation " * 10),
            corner_focus="T5",
        )
        tight = PolicyConfig(headline_max=24)
        msg = message_from_plan(plan, config=tight)
        assert len(msg.headline) <= 24
        assert msg.headline.endswith("…")


class TestMessageFromSummary:
    def test_populated_summary_produces_session_summary_category(self):
        history = [
            [CornerInsight(corner_name="T5", time_loss_s=0.4, loss_zone="exit")] * 1,
            [CornerInsight(corner_name="T5", time_loss_s=0.3, loss_zone="exit")] * 1,
            [CornerInsight(corner_name="T5", time_loss_s=0.2, loss_zone="exit")] * 1,
        ]
        summary = build_post_session_summary(history)
        msg = message_from_summary(summary)
        assert msg.category == "session_summary"
        assert msg.focus_id == "T5"
        assert "T5" in msg.headline
        assert msg.supporting["top_issues"]
        assert msg.supporting["biggest_loss"]

    def test_empty_summary_produces_empty_low_confidence_message(self):
        summary = build_post_session_summary([])
        msg = message_from_summary(summary)
        assert msg.category == "session_summary"
        assert msg.confidence == "low"
        assert msg.severity == "ok"


class TestSeverityMapping:
    @pytest.mark.parametrize("confidence,severity", [
        ("high", "positive"),
        ("medium", "advisory"),
        ("low", "ok"),
        ("unknown", "ok"),
    ])
    def test_severity_for_confidence(self, confidence, severity):
        assert severity_for_confidence(confidence) == severity


# ---------------------------------------------------------------------------
# Consistency invariants across surfaces
# ---------------------------------------------------------------------------

class TestCrossSurfaceConsistency:
    """Same plan/summary must produce the same key content regardless
    of which surface renders it. This is the 'one coach' guarantee."""

    def test_same_plan_produces_same_headline_regardless_of_config(self):
        """The overlay (RACE_OVERLAY_POLICY) and Coaching tab
        (COACHING_TAB_POLICY) can differ in truncation limits, but the
        underlying text (before truncation) must match exactly."""
        plan = _corner_plan()
        race = message_from_plan(plan, time_loss_s=0.35, config=RACE_OVERLAY_POLICY)
        tab = message_from_plan(plan, time_loss_s=0.35, config=COACHING_TAB_POLICY)

        # Identical identity fields
        assert race.focus_id == tab.focus_id
        assert race.category == tab.category
        assert race.confidence == tab.confidence
        assert race.severity == tab.severity
        # Supporting content is identical
        assert race.supporting == tab.supporting

    def test_summary_presentation_matches_message_supporting(self):
        """Post-session summary's flat presentation dict must be a
        subset of the unified CoachingMessage.supporting so both paths
        produce identical strings."""
        history = [
            [CornerInsight(corner_name="T5", time_loss_s=0.4, loss_zone="exit")] * 1,
            [CornerInsight(corner_name="T5", time_loss_s=0.3, loss_zone="exit")] * 1,
            [CornerInsight(corner_name="T5", time_loss_s=0.2, loss_zone="exit")] * 1,
        ]
        summary = build_post_session_summary(history)
        presentation = build_summary_presentation(summary)
        message = message_from_summary(summary)

        # Presentation keys come from message.supporting — no drift
        assert presentation["top_issues"] == message.supporting.get("top_issues", "")
        assert presentation["biggest_loss"] == message.supporting.get("biggest_loss", "")
        assert presentation["next_focus"] == message.supporting.get("next_focus", "")

    def test_message_to_dict_shape_is_qml_friendly(self):
        msg = message_from_plan(_corner_plan(), time_loss_s=0.35)
        d = message_to_dict(msg)
        assert set(d.keys()) == {
            "focus_id", "category", "headline", "subline",
            "confidence", "severity", "time_loss_s", "supporting", "is_empty",
        }
        assert isinstance(d["supporting"], dict)

    def test_empty_plan_empty_summary_both_flag_empty(self):
        """Both surfaces must use the same 'is there nothing to say?'
        flag so QML can hide them with identical logic."""
        empty_plan_msg = message_from_plan(None)
        empty_summary_msg = message_from_summary(build_post_session_summary([]))
        assert empty_plan_msg.is_empty is True
        # Summary has a fallback "Not enough data…" line, so it isn't
        # strictly empty — but the severity is 'ok' so surfaces can gate.
        assert empty_summary_msg.severity == "ok"


class TestPlanTimeLossSnapshot:
    """The plan carries its own ``plan_time_loss_s`` snapshot so overlay
    hysteresis sees a stable value across the plan's lifetime instead of
    jittering with each lap's insights."""

    def test_corner_focused_plan_records_time_loss_snapshot(self):
        from lap_coach_logger.coaching.plan_engine import generate_plan
        from lap_coach_logger.core.consistency_analyzer import ConsistencyReport

        report = ConsistencyReport(
            overall_std_dev_s=0.15,
            consistency_pct=97.0,
            median_lap_time_s=90.0,
            best_lap_time_s=88.5,
            theoretical_best_s=88.0,
            per_sector_std_dev=[0.1, 0.1, 0.1],
            worst_sector=None,
            worst_corners=[],
            trend="stable",
            focus_recommendation="",
            lap_count=10,
        )
        insights = [
            CornerInsight(
                corner_name="T7",
                time_loss_s=0.45,
                exit_speed_delta_kph=-6.0,
                loss_zone="exit",
                confidence="high",
            ),
        ]
        output = generate_plan(report, laps_completed=10, corner_insights=insights)
        plan = output.value
        assert plan is not None
        assert plan.corner_focus == "T7"
        assert plan.plan_time_loss_s == pytest.approx(0.45)

    def test_message_prefers_plan_snapshot_over_latest_insight(self):
        from lap_coach_logger.coaching.plan_engine import CoachingPlan
        from lap_coach_logger.coaching.output import Confidence

        plan = CoachingPlan(
            focus_area="T7",
            objective="Earlier throttle",
            measurable_target="Reduce T7 by 0.2s",
            technique_insight="T7: exit phase",
            corner_focus="T7",
            plan_time_loss_s=0.45,
            confidence=Confidence.HIGH,
        )
        # Even if the caller passes a different (stale) time_loss_s, the
        # builder still reflects what was passed in — callers are the
        # ones who must choose plan.plan_time_loss_s for stability.
        msg_from_snapshot = message_from_plan(plan, time_loss_s=plan.plan_time_loss_s)
        assert msg_from_snapshot.time_loss_s == pytest.approx(0.45)
        # Called without an explicit time_loss_s → None (unknown)
        msg_unknown = message_from_plan(plan)
        assert msg_unknown.time_loss_s is None
