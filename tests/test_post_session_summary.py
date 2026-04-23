"""Tests for post-session coaching summary (Part 5)."""
from __future__ import annotations

import pytest

from lap_coach_logger.coaching.corner_insights import CornerInsight
from lap_coach_logger.coaching.post_session_summary import (
    PostSessionSummary,
    build_post_session_summary,
    summary_to_dict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insight(name: str, loss: float, zone: str = "even", conf: str = "medium") -> CornerInsight:
    return CornerInsight(
        corner_name=name,
        time_loss_s=loss,
        loss_zone=zone,
        confidence=conf,
    )


# ---------------------------------------------------------------------------
# Empty / insufficient data cases
# ---------------------------------------------------------------------------

class TestEmptyCases:
    def test_empty_history_returns_empty_summary(self):
        summary = build_post_session_summary([])
        assert summary.problem_zones == []
        assert summary.largest_loss_area == ""
        assert summary.total_time_on_table_s == 0.0
        assert "Not enough data" in summary.primary_next_session_focus

    def test_fewer_than_three_laps_returns_empty_summary(self):
        history = [[_insight("T5", 0.5)]]
        summary = build_post_session_summary(history)
        assert summary.problem_zones == []

    def test_all_small_losses_returns_empty_problems(self):
        history = [
            [_insight("T1", 0.05)],
            [_insight("T1", 0.04)],
            [_insight("T1", 0.03)],
        ]
        summary = build_post_session_summary(history)
        # No insight passes the noise floor → empty rollup
        assert summary.problem_zones == []
        assert summary.largest_loss_area == ""


# ---------------------------------------------------------------------------
# Populated summaries
# ---------------------------------------------------------------------------

class TestPopulatedSummary:
    def test_top_three_ranked_by_cumulative_loss(self):
        # T5 dominates; T3 second; T8 third. T1 should not appear (only 3 slots).
        history = [
            [_insight("T5", 0.4, zone="exit"), _insight("T3", 0.2), _insight("T8", 0.1)],
            [_insight("T5", 0.3, zone="exit"), _insight("T3", 0.2), _insight("T1", 0.08)],
            [_insight("T5", 0.2, zone="exit"), _insight("T3", 0.1), _insight("T8", 0.1)],
        ]
        summary = build_post_session_summary(history)
        assert len(summary.problem_zones) == 3
        assert summary.problem_zones[0].corner_name == "T5"
        assert summary.problem_zones[0].total_loss_s == pytest.approx(0.9, abs=0.01)
        assert summary.problem_zones[1].corner_name == "T3"
        assert summary.problem_zones[2].corner_name == "T8"

    def test_largest_loss_area_includes_zone_label(self):
        history = [
            [_insight("T5", 0.3, zone="exit")],
            [_insight("T5", 0.4, zone="exit")],
            [_insight("T5", 0.5, zone="exit")],
        ]
        summary = build_post_session_summary(history)
        assert summary.largest_loss_area == "T5 exit"
        assert summary.largest_loss_s == pytest.approx(1.2, abs=0.01)

    def test_primary_focus_names_corner_and_loss(self):
        history = [
            [_insight("T5", 0.4, zone="exit", conf="high")],
            [_insight("T5", 0.3, zone="exit", conf="high")],
            [_insight("T5", 0.2, zone="exit", conf="high")],
        ]
        summary = build_post_session_summary(history)
        focus = summary.primary_next_session_focus
        assert "T5" in focus
        assert "0.9" in focus or "0.9s" in focus  # total loss

    def test_summary_dict_is_qml_friendly(self):
        history = [
            [_insight("T5", 0.3, zone="exit")],
            [_insight("T5", 0.3, zone="exit")],
            [_insight("T5", 0.3, zone="exit")],
        ]
        summary = build_post_session_summary(history)
        d = summary_to_dict(summary)
        # Shape check — all keys present and serialisable types
        assert {
            "problem_zones",
            "largest_loss_area",
            "largest_loss_s",
            "primary_next_session_focus",
            "total_time_on_table_s",
            "lap_sample_count",
            "presentation",
        }.issubset(set(d.keys()))
        assert isinstance(d["problem_zones"], list)
        assert isinstance(d["primary_next_session_focus"], str)


# ---------------------------------------------------------------------------
# Glanceable presentation mapping
# ---------------------------------------------------------------------------

class TestPresentation:
    def test_presentation_produces_three_lines(self):
        from lap_coach_logger.coaching.post_session_summary import (
            build_summary_presentation,
        )

        history = [
            [_insight("T5", 0.4, zone="exit"), _insight("T3", 0.2), _insight("T8", 0.15)],
            [_insight("T5", 0.3, zone="exit"), _insight("T3", 0.2), _insight("T1", 0.1)],
            [_insight("T5", 0.2, zone="exit"), _insight("T3", 0.1), _insight("T8", 0.12)],
        ]
        summary = build_post_session_summary(history)
        p = build_summary_presentation(summary)

        # Three distinct, short fields — no dense report
        assert set(p.keys()) == {"top_issues", "biggest_loss", "next_focus"}
        assert "T5" in p["top_issues"]
        assert "T3" in p["top_issues"]
        assert "T5" in p["biggest_loss"]
        assert p["next_focus"]  # non-empty

    def test_presentation_is_empty_when_no_problems(self):
        from lap_coach_logger.coaching.post_session_summary import (
            build_summary_presentation,
        )
        summary = build_post_session_summary([])
        p = build_summary_presentation(summary)
        assert p["top_issues"] == ""
        assert p["biggest_loss"] == ""
        # next_focus still explains why (Not enough data…)
        assert p["next_focus"]

    def test_next_focus_keeps_only_actionable_sentence(self):
        from lap_coach_logger.coaching.post_session_summary import (
            build_summary_presentation,
        )
        history = [
            [_insight("T5", 0.4, zone="exit", conf="high")],
            [_insight("T5", 0.3, zone="exit", conf="high")],
            [_insight("T5", 0.2, zone="exit", conf="high")],
        ]
        summary = build_post_session_summary(history)
        p = build_summary_presentation(summary)
        # The primary focus sentence can be 2 sentences; presentation
        # should reduce to the action-style trailing one.
        assert p["next_focus"]
        # Should not contain both a "Next session:" and " Earlier throttle"
        # segment simultaneously — we keep one glanceable sentence.
        assert p["next_focus"].count("Next session") <= 1
