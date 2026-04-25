"""T073: Review page no longer shows deep-analysis tabs.

The Telemetry / Setup / Engineering tabs were placeholders showing
"Coming from legacy migration" text and no real bindings. After
T071 (compact summary) + T072 (prominent webapp CTA), they
duplicate-and-undermine the user signal "deep analysis lives in
the webapp." T073 removes them entirely.

After this task the only tabs are **Overview** and **Laps**.

UI rendering can't be tested without QApplication, but content
assertions on the QML source pin the removal so future PRs can't
quietly re-introduce the tabs.
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
# SectionTabs model: only Overview + Laps
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "removed_label", ['"Telemetry"', '"Setup"', '"Engineering"']
)
def test_section_tabs_no_longer_lists_removed_label(
    review_qml_text: str, removed_label: str
) -> None:
    """SectionTabs model entries used quoted strings as labels;
    matching ``"Telemetry"`` etc. catches the model entry without
    flagging unrelated mentions."""
    assert removed_label not in review_qml_text


def test_section_tabs_still_lists_overview(review_qml_text: str) -> None:
    assert '"Overview"' in review_qml_text


def test_section_tabs_still_lists_laps(review_qml_text: str) -> None:
    assert '"Laps"' in review_qml_text


# ---------------------------------------------------------------------------
# sectionIndexMap: only the two surviving sections
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "removed_id", ['"telemetry":', '"setup":', '"engineering":']
)
def test_section_index_map_no_longer_lists_removed_id(
    review_qml_text: str, removed_id: str
) -> None:
    """``sectionIndexMap`` keys are JSON-style ``"id":`` patterns;
    matching the trailing colon catches the map entry without
    matching unrelated mentions in comments."""
    assert removed_id not in review_qml_text


def test_section_index_map_still_lists_overview_and_laps(
    review_qml_text: str,
) -> None:
    assert '"overview":' in review_qml_text
    assert '"laps":' in review_qml_text


# ---------------------------------------------------------------------------
# Placeholder Item blocks: gone entirely
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "marker",
    [
        "// --- Telemetry (placeholder",
        "// --- Setup (placeholder",
        "// --- Engineering (placeholder",
    ],
)
def test_placeholder_block_marker_removed(
    review_qml_text: str, marker: str
) -> None:
    """The T066-audit comments marked each block as
    ``(placeholder, removed by T073)``. After T073, the comments
    AND the blocks themselves must be gone."""
    assert marker not in review_qml_text


def test_placeholder_legacy_text_is_gone(review_qml_text: str) -> None:
    """All three placeholder blocks shared the same fallback
    text — its disappearance is the easiest single-string
    confirmation that the blocks went away."""
    assert "Coming from legacy migration" not in review_qml_text
