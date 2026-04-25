"""T074: ``load_session_review`` emits review-page contract fields.

The Review page QML reads ``reviewVM.data.quality_grade`` (header
badge color logic) and ``reviewVM.data.best_lap_formatted`` (BEST
LAP big number). Until T074 the loader emitted ``quality_classification``
and ``best_lap_time_s`` (raw seconds) instead, so the bindings silently
fell through to their ``||`` defaults — empty badge, em-dash for best
lap. This was a pure contract mismatch, not a missing data path.

T074 adds two thin derived keys to the loader output:
- ``quality_grade``: A / B+ / C / "" derived from ``quality_classification``
- ``best_lap_formatted``: ``M:SS.mmm`` derived from ``best_lap_time_s``

The raw fields stay in the dict unchanged so existing callers and
tests continue to pass — these are pure additions, not renames.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lap_coach_logger.core.session_review import load_session_review


def _write_bundle(
    folder: Path,
    *,
    quality_classification: str | None = "accepted",
    best_lap_time_s: float | None = 83.456,
) -> Path:
    """Build the minimal three-file bundle the loader expects.

    Only the two fields under T074 test here vary — everything else
    is filler that keeps the loader happy. ``session.json`` is the
    manifest the finalizer writes; ``quality_report.json`` carries
    the classification verdict; ``analysis.json`` is read but its
    contents don't affect either field under test.
    """
    folder.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {
        "session_id": "t074-bundle",
        "schema_version": "2.0",
        "review_status": "ready",
        "best_lap_time_s": best_lap_time_s,
        "session": {
            "session_uid": "t074-bundle",
            "duration_s": 120.0,
            "sample_count": 100,
            "lap_count": 3,
        },
        "raw_source": {
            "sim_display_name": "iRacing",
            "raw_track": "Spa",
            "raw_car": "BMW M4 GT3",
            "session_type_raw": "Race",
        },
    }

    quality_report: dict[str, object] = {
        "recommended_classification": quality_classification,
        "warnings": [],
        "rejection_reasons": [],
    }

    (folder / "session.json").write_text(json.dumps(manifest), encoding="utf-8")
    (folder / "quality_report.json").write_text(
        json.dumps(quality_report), encoding="utf-8"
    )
    (folder / "analysis.json").write_text(json.dumps({}), encoding="utf-8")
    return folder


# ---------------------------------------------------------------------------
# quality_grade derivation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("classification", "expected_grade"),
    [
        ("accepted", "A"),
        ("accepted_with_warnings", "B+"),
        ("rejected", "C"),
        ("-", ""),
    ],
)
def test_quality_grade_derived_from_classification(
    tmp_path: Path, classification: str, expected_grade: str
) -> None:
    """The QML colour logic keys off A / A+ (acidGreen) and B+
    (marshalYellow); anything else falls through to steel. The
    mapping above mirrors the four classification verdicts the
    quality report can emit.

    ``"-"`` (no classification yet) and a missing classification
    both collapse to ``""`` so the QML hides the badge entirely
    rather than rendering a meaningless steel-coloured pill.
    """
    bundle = _write_bundle(tmp_path, quality_classification=classification)

    review = load_session_review(bundle)

    assert review["quality_grade"] == expected_grade


def test_quality_grade_for_missing_classification_is_blank(
    tmp_path: Path,
) -> None:
    """When the quality report has no recommended classification at
    all (for example, a still-processing or pre-quality-report
    bundle), the loader falls back to ``"-"`` — which T074 maps to
    a blank grade so the badge stays hidden."""
    bundle = _write_bundle(tmp_path, quality_classification=None)

    review = load_session_review(bundle)

    assert review["quality_grade"] == ""


# ---------------------------------------------------------------------------
# best_lap_formatted derivation
# ---------------------------------------------------------------------------


def test_best_lap_formatted_uses_minutes_seconds_milliseconds(
    tmp_path: Path,
) -> None:
    """Format mirrors ``dashboard_live_processor._format_lap_time``
    (the canonical motorsport ``M:SS.mmm`` shape) so a 83.456 s lap
    renders as ``1:23.456`` — not ``83.456s`` like the archive list
    helper does.

    The archive list (HistoryPage) is a tabular view where ``s``
    suffix matters; the review page has a giant 40 px BEST LAP
    number where the leading-minutes form reads better at a glance.
    """
    bundle = _write_bundle(tmp_path, best_lap_time_s=83.456)

    review = load_session_review(bundle)

    assert review["best_lap_formatted"] == "1:23.456"


def test_best_lap_formatted_pads_seconds_below_ten(tmp_path: Path) -> None:
    """A 65.04 s lap should pad to ``1:05.040`` (zero-padded
    seconds and milliseconds) so the column doesn't jiggle when
    laps cross the :10 boundary mid-session."""
    bundle = _write_bundle(tmp_path, best_lap_time_s=65.04)

    review = load_session_review(bundle)

    assert review["best_lap_formatted"] == "1:05.040"


def test_best_lap_formatted_for_missing_best_is_blank(tmp_path: Path) -> None:
    """No best lap (no completed laps yet, or rejected bundle) ⇒
    blank string so the QML's ``|| "—"`` fallback shows the em
    dash. Returning ``"0:00.000"`` would falsely advertise a
    lightning-fast lap."""
    bundle = _write_bundle(tmp_path, best_lap_time_s=None)

    review = load_session_review(bundle)

    assert review["best_lap_formatted"] == ""


def test_best_lap_formatted_for_zero_or_negative_is_blank(
    tmp_path: Path,
) -> None:
    """A best lap of 0 or negative seconds is a sentinel for
    "no valid timed lap" — collapse it to blank so the QML shows
    the em-dash placeholder rather than ``0:00.000``."""
    bundle = _write_bundle(tmp_path, best_lap_time_s=0.0)

    review = load_session_review(bundle)

    assert review["best_lap_formatted"] == ""


# ---------------------------------------------------------------------------
# Backwards compatibility: raw fields still present
# ---------------------------------------------------------------------------


def test_raw_quality_classification_field_still_emitted(tmp_path: Path) -> None:
    """T074 *adds* ``quality_grade`` — the raw
    ``quality_classification`` must keep flowing for existing
    callers (sync gating, archive helper, etc.)."""
    bundle = _write_bundle(tmp_path, quality_classification="accepted")

    review = load_session_review(bundle)

    assert review["quality_classification"] == "accepted"


def test_raw_best_lap_time_s_field_still_emitted(tmp_path: Path) -> None:
    """T074 *adds* ``best_lap_formatted`` — the raw
    ``best_lap_time_s`` must keep flowing for chart logic and
    cross-session comparisons."""
    bundle = _write_bundle(tmp_path, best_lap_time_s=83.456)

    review = load_session_review(bundle)

    assert review["best_lap_time_s"] == 83.456
