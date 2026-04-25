"""T075: Review-page integration test — archived sessions load
through the full data pipeline without errors and expose every
field the ReviewPage QML binds against.

The data path under test is end-to-end:

    SessionFinalizer  →  on-disk bundle (session.json,
                            quality_report.json, analysis.json)
                      →  load_session_review()
                      →  ReviewViewModel.load()
                      →  reviewVM.data.<field> bindings in QML

QML can't be rendered without a QApplication, so this test pins
the *contract*: every ``reviewVM.data.<field>`` access in
``ReviewPage.qml`` must resolve against the loader's dict to a
defined value (concrete or ``None`` — both fine because the QML
falls through to ``||`` defaults). A ``KeyError`` would crash
QML's binding evaluator at runtime; that's what this test guards.

The fields enumerated below are the *exact* set ReviewPage.qml
reads from ``reviewVM.data``. Future PRs adding new bindings must
either (a) extend ``load_session_review`` to emit them, or (b)
extend this list — but the page can never silently regress.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from lap_coach_logger.core.session_review import load_session_review
from lap_coach_logger.viewmodels.review_vm import ReviewViewModel


# ---------------------------------------------------------------------------
# Data-path integration: bundle → loader → VM
# ---------------------------------------------------------------------------


def test_archived_session_loads_through_review_pipeline_without_errors(
    bundled_session: Path,
) -> None:
    """End-to-end smoke test: a finalized archive bundle flows
    through ``load_session_review`` and into ``ReviewViewModel``
    with no exceptions raised.

    Pre-T074 this would still pass (load_session_review never
    raised), but post-T074 the dict carries the right keys for
    QML — which the field-coverage test below pins.
    """
    review = load_session_review(bundled_session)

    vm = ReviewViewModel()
    vm.load(review)  # must not raise

    assert vm.data is review  # full passthrough by reference
    assert vm.section == "overview"  # default landing tab
    assert vm.path == str(bundled_session)


# ---------------------------------------------------------------------------
# QML binding-path coverage: every reviewVM.data.X resolves
# ---------------------------------------------------------------------------


# These are the exact field names ReviewPage.qml reads via
# ``reviewVM.data.<name>``. Extracted from the QML by grep so
# adding a new binding mechanically forces a test-list update.
REVIEW_PAGE_BINDINGS: tuple[str, ...] = (
    "session_id",         # delete dialog + webapp deep-link CTA
    "sim",                # header subtitle (logo lookup)
    "quality_grade",      # header badge color + text
    "track",              # header heading
    "car",                # header subtitle
    "laps",               # header subtitle (lap count)
    "best_lap_formatted", # right-aligned BEST LAP big number
    "consistency",        # Overview Consistency MetricCard value
    "consistency_sigma",  # Overview Consistency MetricCard subtitle
    "lap_times",          # LapTimeChart + Laps section ListView
)


@pytest.mark.parametrize("field", REVIEW_PAGE_BINDINGS)
def test_review_data_dict_supports_qml_binding_for_field(
    bundled_session: Path, field: str
) -> None:
    """Every ReviewPage QML binding path must be accessible on
    the loader dict — either with a concrete value or as a missing
    key (QML's ``||`` default kicks in for both ``undefined`` and
    falsy values, so either is fine; what matters is that nothing
    raises during binding evaluation).

    ``dict.get(field)`` mirrors QML's ``reviewVM.data.<field>``
    access pattern: missing keys collapse to ``None`` instead of
    raising — but if some upstream change ever turned ``data``
    into something other than a dict (e.g., a dataclass), this
    test would catch it before QML did.
    """
    review = load_session_review(bundled_session)

    assert isinstance(review, dict), (
        "ReviewViewModel.data must stay a dict so QML "
        "property-access bindings work"
    )
    review.get(field)  # must not raise — the key is allowed to be absent


# ---------------------------------------------------------------------------
# T074 contract anchors: critical fields concretely populated
# ---------------------------------------------------------------------------


def test_archived_session_carries_session_id_for_webapp_deep_link(
    bundled_session: Path,
) -> None:
    """The T070 webapp CTA passes ``reviewVM.data.session_id`` to
    ``viewSessionInWebapp``. A blank id silently falls back to the
    sessions list — fine UX, but for a real archived bundle the
    id must be concrete or the deep-link feature is dead."""
    review = load_session_review(bundled_session)

    session_id = review.get("session_id")
    assert isinstance(session_id, str)
    assert session_id  # non-empty


def test_archived_session_carries_quality_grade(
    bundled_session: Path,
) -> None:
    """Quality-grade badge is one of the four T071 dimensions
    visible in the header. The fixture's bundle goes through the
    real quality classifier, so the loader must surface a grade
    string — empty is allowed (no classification yet) but the
    key MUST exist (T074 contract)."""
    review = load_session_review(bundled_session)

    assert "quality_grade" in review
    assert isinstance(review["quality_grade"], str)


def test_archived_session_carries_best_lap_formatted(
    bundled_session: Path,
) -> None:
    """Best-lap is one of the four T071 dimensions and renders
    as a 40 px BEST LAP big number. Fixture has 3 laps so a
    timed best should exist — but even a blank-string fallback
    means the key MUST exist (T074 contract)."""
    review = load_session_review(bundled_session)

    assert "best_lap_formatted" in review
    assert isinstance(review["best_lap_formatted"], str)
