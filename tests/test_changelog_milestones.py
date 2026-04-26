"""T200: CHANGELOG.md has milestone entries for M1 + M2.

The roadmap (``docs/roadmap/04-ROADMAP-6MO.md``) divides
delivery into six 30-day milestones:

- **M1 FOUNDATION** (Apr 23 → May 22): P0 defects, schemas
  (``lap-schemas``), Bundle v2 ingest, packaging hardening.
- **M2 INTELLIGENCE** (May 23 → Jun 22): live telemetry
  processor, ``next_actions`` engine, upload queue, private
  beta.
- M3 Public Beta, M4 Bridge, M5 V1 Release, M6 Scale.

The CHANGELOG already has version entries (2.0.0, 1.1.0).
T200 adds *milestone* entries at the top — a different axis
that groups cross-cutting deliverables. Versions tag
releasable artifacts; milestones group strategic outcomes.

T200 pins:

1. CHANGELOG.md exists at the repo root.
2. The file has an "Unreleased" / milestone section above
   the per-version sections.
3. The Unreleased block contains an M1 entry mentioning the
   FOUNDATION theme keywords.
4. The Unreleased block contains an M2 entry mentioning the
   INTELLIGENCE theme keywords.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


_CHANGELOG_PATH = (
    Path(__file__).resolve().parents[1] / "CHANGELOG.md"
)


@pytest.fixture(scope="module")
def changelog_text() -> str:
    assert _CHANGELOG_PATH.is_file(), (
        f"CHANGELOG.md must exist at {_CHANGELOG_PATH}"
    )
    return _CHANGELOG_PATH.read_text(encoding="utf-8")


def _unreleased_block(text: str) -> str:
    """Slice the leading 'Unreleased' / milestone section —
    everything from the first 'Unreleased' heading down to
    the next H2 (which would be a per-version entry).
    """
    match = re.search(
        r'^##\s+(?:\[?Unreleased\]?|Unreleased)[\s\S]*?'
        r'(?=^##\s+(?:\[?\d|\d|v\d))',
        text,
        re.MULTILINE | re.IGNORECASE,
    )
    if match is None:
        # Fall back: the whole pre-version-headings region.
        # Find the first version heading and slice everything
        # above it.
        first_version = re.search(
            r'^##\s+(?:\[?\d|\d|v\d)',
            text,
            re.MULTILINE,
        )
        if first_version:
            return text[: first_version.start()]
        return text
    return match.group(0)


# -- existence + structure --------------------------------------------


def test_changelog_exists() -> None:
    """CHANGELOG.md is the canonical history doc — must be at
    the repo root where conventional tooling expects it."""
    assert _CHANGELOG_PATH.is_file(), (
        f"CHANGELOG.md must exist at {_CHANGELOG_PATH}"
    )


def test_changelog_has_unreleased_section(changelog_text: str) -> None:
    """A leading 'Unreleased' or milestone section is the
    standard place to track work-in-progress milestones
    before they get a version tag."""
    assert re.search(
        r'^##\s+(?:\[?Unreleased\]?|Unreleased|Milestones?)',
        changelog_text,
        re.MULTILINE | re.IGNORECASE,
    ), (
        "CHANGELOG.md must have a leading `## Unreleased` (or "
        "`## Milestones`) section above per-version entries — "
        "milestone tracking belongs there"
    )


# -- milestone entries -----------------------------------------------


def test_changelog_has_m1_entry(changelog_text: str) -> None:
    """The Unreleased / milestones block must reference M1
    (FOUNDATION). Tolerant on heading style: ``### M1``,
    ``### M1 — Foundation``, ``- **M1**: ...`` all qualify."""
    block = _unreleased_block(changelog_text)
    assert re.search(
        r'\bM1\b',
        block,
    ), (
        "CHANGELOG.md's Unreleased section must mention M1 "
        "(FOUNDATION milestone) — see "
        "docs/roadmap/04-ROADMAP-6MO.md"
    )


def test_changelog_m1_mentions_foundation_themes(
    changelog_text: str,
) -> None:
    """The M1 entry must mention at least one of the
    FOUNDATION theme keywords so the milestone is connected
    to its actual deliverables, not just a label."""
    block = _unreleased_block(changelog_text)
    # Find the M1 sub-block: from M1 line down to the next
    # 'M' followed by digit (next milestone) or end of block.
    m1_match = re.search(
        r'\bM1\b[\s\S]*?(?=\bM[2-6]\b|\Z)',
        block,
    )
    assert m1_match is not None, "precondition (M1 mention required)"
    m1_text = m1_match.group(0).lower()
    foundation_keywords = (
        "foundation", "p0", "schema", "bundle", "ingest",
        "audit", "lap-schemas", "fastapi",
    )
    matched = [k for k in foundation_keywords if k in m1_text]
    assert matched, (
        f"M1 entry must mention at least one FOUNDATION "
        f"theme keyword (any of {foundation_keywords}); "
        f"otherwise the entry is a label without content"
    )


def test_changelog_has_m2_entry(changelog_text: str) -> None:
    """The Unreleased / milestones block must reference M2
    (INTELLIGENCE)."""
    block = _unreleased_block(changelog_text)
    assert re.search(
        r'\bM2\b',
        block,
    ), (
        "CHANGELOG.md's Unreleased section must mention M2 "
        "(INTELLIGENCE milestone)"
    )


def test_changelog_m2_mentions_intelligence_themes(
    changelog_text: str,
) -> None:
    """The M2 entry must mention at least one INTELLIGENCE
    theme keyword."""
    block = _unreleased_block(changelog_text)
    m2_match = re.search(
        r'\bM2\b[\s\S]*?(?=\bM[3-6]\b|\Z)',
        block,
    )
    assert m2_match is not None, "precondition (M2 mention required)"
    m2_text = m2_match.group(0).lower()
    intelligence_keywords = (
        "intelligence", "live processor", "live telemetry",
        "next_actions", "next-actions", "upload queue",
        "private beta", "coaching",
    )
    matched = [k for k in intelligence_keywords if k in m2_text]
    assert matched, (
        f"M2 entry must mention at least one INTELLIGENCE "
        f"theme keyword (any of {intelligence_keywords})"
    )


# -- version entries preserved ---------------------------------------


def test_changelog_keeps_existing_version_entries(
    changelog_text: str,
) -> None:
    """T200 *adds* milestone entries above the per-version
    history — it must not displace the 2.0.0 / 1.1.0 / etc.
    sections that were already there."""
    assert re.search(
        r'^##\s+(?:\[?2\.0\.0\]?|2\.0\.0)',
        changelog_text,
        re.MULTILINE,
    ), (
        "CHANGELOG.md must still have the 2.0.0 version "
        "entry — milestone entries are added above, not "
        "replacing the per-version history"
    )
