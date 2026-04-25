"""T072: Review page surfaces a prominent "See full analysis in
webapp" CTA wired to the T070 ``viewSessionInWebapp`` slot.

T070 shipped the slot (with safe blank-id fallback to the sessions
list); T071 trimmed the Overview cards down to Consistency. T072
fills the freed-up space with a primary-style CTA so users
understand "the full analysis lives in the webapp".

UI rendering can't be tested without a QApplication, but content
assertions on the QML source pin the CTA's presence + wiring
intent so future PRs can't quietly drop or break it.
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
# CTA presence + copy
# ---------------------------------------------------------------------------


def test_overview_contains_full_analysis_cta_text(review_qml_text: str) -> None:
    """The CTA copy is the load-bearing user signal — it tells the
    user *why* the desktop's compact summary is intentionally
    minimal. Pinning the exact text guards against accidental copy
    drift during refactors."""
    assert "See full analysis in webapp" in review_qml_text


# ---------------------------------------------------------------------------
# CTA wiring: must call viewSessionInWebapp with the session_id
# ---------------------------------------------------------------------------


def test_overview_cta_wires_to_view_session_in_webapp(
    review_qml_text: str,
) -> None:
    """The CTA's onClicked must invoke the T070 ServiceViewModel
    slot. Pinning the slot name catches regressions where a
    refactor renames the slot without updating QML callers."""
    assert "serviceVM.viewSessionInWebapp" in review_qml_text


def test_overview_cta_passes_session_id_from_review_data(
    review_qml_text: str,
) -> None:
    """The deep-link version of viewSessionInWebapp expects a
    session_id; passing ``reviewVM.data.session_id`` (with a safe
    fallback to "") gets the user to the per-session detail page
    when known, list view otherwise."""
    assert "reviewVM.data.session_id" in review_qml_text


# ---------------------------------------------------------------------------
# Prominence: must live in the Overview section (not buried elsewhere)
# ---------------------------------------------------------------------------


def test_cta_is_inside_overview_section_not_in_a_tab(
    review_qml_text: str,
) -> None:
    """The CTA must appear *before* the ``// --- Laps ---`` marker
    so it sits in the Overview ScrollView (the section users land
    on). Inside Laps / Telemetry / Setup / Engineering it would be
    invisible until the user explicitly switched tabs."""
    cta_idx = review_qml_text.find("See full analysis in webapp")
    laps_idx = review_qml_text.find("// --- Laps ---")
    assert cta_idx > 0, "CTA copy must be present"
    assert laps_idx > 0, "Laps section marker should still exist"
    assert cta_idx < laps_idx, "CTA must be in Overview, not later sections"
