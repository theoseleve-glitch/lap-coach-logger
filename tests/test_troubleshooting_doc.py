"""T230: TROUBLESHOOTING.md covers the common issues.

Pins minimum coverage of the troubleshooting doc so it stays
useful instead of drifting toward "stub with three entries":

  - At least 12 distinct issues (sections starting with ``## ``)
  - Each of the recurring user-issue categories has at least
    one section: install, tray, sims, sessions, overlays, sync,
    telemetry-consent, config-backup, accessibility, logs
  - Doc has a "Last reviewed: YYYY-MM-DD" marker

This is coverage-shape-only — humans still write and maintain
the prose. The test catches the silent rot where a feature
ships, generates a known support question, and never makes it
into the doc.
"""
from __future__ import annotations

import re
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOC_PATH = _REPO_ROOT / "TROUBLESHOOTING.md"


def _read_doc() -> str:
    assert _DOC_PATH.exists(), f"missing {_DOC_PATH}"
    return _DOC_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Section count
# ---------------------------------------------------------------------------


def test_doc_has_at_least_twelve_issue_sections() -> None:
    """Each ``## `` heading is one troubleshooting issue.
    Twelve is the minimum bar for "covers common issues" —
    we have more than 12 categories of regular support
    questions (see test_doc_covers_each_recurring_category)."""
    doc = _read_doc()
    sections = re.findall(r"^##\s+\S", doc, re.MULTILINE)
    assert len(sections) >= 12, (
        f"TROUBLESHOOTING.md has only {len(sections)} '## '-headed "
        f"issue sections; expected >= 12 to count as 'covers "
        f"common issues'. Add more entries from the support FAQ."
    )


# ---------------------------------------------------------------------------
# Recurring category coverage
# ---------------------------------------------------------------------------


# Each tuple is (category_label, set_of_acceptable_keywords).
# A category passes if ANY of its keywords appear in the doc.
# Keywords are lowercase substring checks.
_REQUIRED_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("install / module not found", ("module named", "pip install", "src layout")),
    ("tray / minimize behavior", ("tray", "system tray")),
    ("sim adapter detection", ("iracing", "acc", "assetto corsa", "lmu")),
    ("sessions in history", ("history", "no sessions appear", "session folder")),
    ("overlays not visible", ("overlay", "not visible", "wrong position")),
    ("sync to webapp", ("sync", "webapp", "upload")),
    ("telemetry consent / opt-in", ("telemetry", "consent", "opt-in", "opt in")),
    ("config backup", ("config backup", "config.json.v1.bak", ".bak")),
    ("accessibility / high contrast", ("accessibility", "high contrast", "high-contrast", "screen reader")),
    ("logs / diagnostics", ("log", "lap_coach_logger.log", "diagnostic")),
)


def test_doc_covers_each_recurring_category() -> None:
    """Every category in the support-FAQ-ish bucket must show
    up in the doc. Catches 'we shipped feature X but the
    troubleshooting doc still doesn't mention it'."""
    doc = _read_doc().lower()
    missing: list[str] = []
    for label, keywords in _REQUIRED_CATEGORIES:
        if not any(k in doc for k in keywords):
            missing.append(label)
    assert not missing, (
        f"TROUBLESHOOTING.md is missing coverage of these "
        f"recurring user-issue categories: {missing}. Each "
        f"should have at least one '## '-headed section."
    )


# ---------------------------------------------------------------------------
# Freshness marker
# ---------------------------------------------------------------------------


def test_doc_has_last_reviewed_marker() -> None:
    """Same drift-prevention as T227-T229: explicit date so
    future readers can spot a stale doc at a glance."""
    doc = _read_doc()
    pattern = r"Last reviewed:\s*\d{4}-\d{2}-\d{2}"
    assert re.search(pattern, doc), (
        "TROUBLESHOOTING.md is missing a 'Last reviewed: "
        "YYYY-MM-DD' line. Add one near the top."
    )
