"""T071: Review page Overview shows ONLY the compact summary
(laps + best + consistency + DQ).

Header bar already carries three of the four dimensions (laps,
best_lap_formatted, quality_grade). The Overview content keeps
Consistency + the LapTimeChart and drops the Median Lap / Clean
Laps / Data Size cards.

UI tests can't render QML without a QApplication, but file-content
assertions are cheap and pin the cleanup intent: future PRs can't
quietly re-introduce the dropped cards without updating the
assertion.
"""
from __future__ import annotations

from pathlib import Path

import pytest


_REVIEW_PAGE_QML = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Pages" / "ReviewPage.qml"
)


@pytest.fixture(scope="module")
def review_qml_text() -> str:
    return _REVIEW_PAGE_QML.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Compact-summary cards: only Consistency stays in Overview
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dropped_label", ["Median Lap", "Clean Laps", "Data Size"])
def test_overview_no_longer_carries_dropped_metric_card(
    review_qml_text: str, dropped_label: str
) -> None:
    """Median Lap / Clean Laps / Data Size are replaced by the
    "See full analysis in webapp" CTA path (T072).

    Match against the QML ``label:`` property so an explanatory
    comment that mentions the dropped names is allowed.
    """
    assert f'label: "{dropped_label}"' not in review_qml_text


def test_overview_still_shows_consistency_card(review_qml_text: str) -> None:
    """Consistency is one of the four T071 dimensions and must stay."""
    assert 'label: "Consistency"' in review_qml_text


def test_lap_time_chart_remains_for_visual_support(
    review_qml_text: str,
) -> None:
    """The chart visualises laps + best + consistency — it's the
    visual summary that backs the four numeric dimensions."""
    assert "Components.LapTimeChart" in review_qml_text


# ---------------------------------------------------------------------------
# Header dimensions already present (regression guards)
# ---------------------------------------------------------------------------


def test_header_still_shows_best_lap(review_qml_text: str) -> None:
    """Best lap is one of the four T071 dimensions; lives in the
    header (right-aligned column)."""
    assert "best_lap_formatted" in review_qml_text


def test_header_still_shows_quality_grade_badge(review_qml_text: str) -> None:
    """DQ (Data Quality grade) is one of the four T071 dimensions;
    lives in the header as a badge next to the track name."""
    assert "quality_grade" in review_qml_text


def test_header_still_shows_lap_count(review_qml_text: str) -> None:
    """Laps count is one of the four T071 dimensions; lives in the
    header subtitle as ``<n> laps``."""
    assert "laps" in review_qml_text
