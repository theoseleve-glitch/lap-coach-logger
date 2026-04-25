"""T147: Strategy view in desktop review — compact summary.

The desktop review page already shows Overview + Laps; T147
adds a Strategy section that surfaces the Q102 trio T144 / T145
/ T146 wired into the bundle:

- ``race_strategy`` — pre-race plan
- ``actual_pit_events`` — what actually happened
- ``plan_vs_actual`` — precomputed delta summary

The webapp still owns the deep analysis (per Q95 / ADR-002);
the desktop section is a *compact* summary so the driver
sees "you planned X, actual was Y" without leaving the
desktop. T021 in the broader roadmap describes the same
intent for the webapp full view.

QML rendering tests need a Qt visual context, which the test
runner doesn't have — so this file pins the file-content of
``ReviewPage.qml`` (regex / substring) the same way T141 / T127
do. Every wiring the section depends on must show up:

- the section is registered in the index map and tab list
  so SectionTabs renders + StackLayout switches
- the view binds to ``reviewVM.data.race_strategy`` and
  ``reviewVM.data.plan_vs_actual`` (the bundle keys T144 /
  T146 emit)
- an empty state is present for sessions that never captured
  a plan
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REVIEW_PAGE = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Pages" / "ReviewPage.qml"
)


@pytest.fixture(scope="module")
def review_qml() -> str:
    return _REVIEW_PAGE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Section registration
# ---------------------------------------------------------------------------


def test_section_index_map_registers_strategy(review_qml: str) -> None:
    """Without a ``strategy`` key in ``sectionIndexMap`` the
    StackLayout falls back to index 0 (overview) on the
    section transition — the new content would never surface.
    Tolerant of formatting (single line vs. multi-line)."""
    pattern = r'"strategy"\s*:\s*\d+'
    assert re.search(pattern, review_qml), (
        f"sectionIndexMap must register a 'strategy' entry; missing "
        f"in {_REVIEW_PAGE}"
    )


def test_section_tabs_model_includes_strategy_tab(review_qml: str) -> None:
    """SectionTabs renders from a model dictionary; without a
    'strategy' entry the user can't navigate to the section
    even if the StackLayout has the content."""
    pattern = r'\{\s*id\s*:\s*"strategy"\s*,\s*label\s*:\s*"Strategy"\s*\}'
    assert re.search(pattern, review_qml), (
        "SectionTabs model must declare "
        "{ id: \"strategy\", label: \"Strategy\" }"
    )


# ---------------------------------------------------------------------------
# Bundle data wiring
# ---------------------------------------------------------------------------


def test_strategy_section_reads_race_strategy_from_review_data(
    review_qml: str,
) -> None:
    """T144's ``race_strategy`` bundle key surfaces here. The
    Strategy section reads the plan inputs (planned stops /
    fuel) from ``reviewVM.data.race_strategy``."""
    assert "reviewVM.data.race_strategy" in review_qml, (
        "Strategy section must read reviewVM.data.race_strategy"
    )


def test_strategy_section_reads_plan_vs_actual_from_review_data(
    review_qml: str,
) -> None:
    """T146's precomputed delta is the headline of the section
    — driver sees the X/Y comparison without recomputing."""
    assert "reviewVM.data.plan_vs_actual" in review_qml, (
        "Strategy section must read reviewVM.data.plan_vs_actual"
    )


# ---------------------------------------------------------------------------
# Empty state for sessions without a plan
# ---------------------------------------------------------------------------


def test_strategy_section_renders_an_empty_state(review_qml: str) -> None:
    """Many sessions (free practice, single-stint races) won't
    ship a strategy. The section must render an explicit empty
    state rather than a blank pane — tolerant of phrasing
    (e.g., 'No strategy', 'No race strategy plan'). The marker
    string only needs to mention that strategy is absent."""
    assert re.search(
        r"No\s+(?:race\s+)?strategy\b", review_qml, re.IGNORECASE
    ), (
        "Strategy section must render an empty-state message "
        "for sessions without a plan"
    )


# ---------------------------------------------------------------------------
# Section content presence
# ---------------------------------------------------------------------------


def test_strategy_section_surfaces_plan_vs_actual_counts(
    review_qml: str,
) -> None:
    """The compact-summary headline is the planned-vs-actual
    stop count (T146 exposes ``planned_stops`` /
    ``actual_stops`` at the top level of the summary). Pin
    that the QML actually references one of those fields so
    the driver sees the headline number."""
    assert (
        "planned_stops" in review_qml or "actual_stops" in review_qml
    ), (
        "Strategy section must surface plan-vs-actual stop "
        "counts (planned_stops / actual_stops from T146)"
    )
