"""T228: SESSION_LIFECYCLE.md exists and matches the FSM in code.

Pins the doc -> code contract for the session state machine so
the doc stays a useful reference instead of rotting.

Specifically:

  - Every ``SessionState`` enum value appears in the doc by name
  - Every allowed transition in ``_TRANSITIONS`` is mentioned
    (either as ``A -> B`` or ``A → B``)
  - Doc has a "Last reviewed: YYYY-MM-DD" line so future readers
    can spot stale prose at a glance

Same pattern as T227 (OVERLAY_PLATFORM.md): the test catches
silent rot where a state or transition is added in code but
never makes it into the prose. Humans still write the prose;
the test only enforces structural references.
"""
from __future__ import annotations

import re
from pathlib import Path

from lap_coach_logger.core.session_state import SessionState
from lap_coach_logger.core.session_state import _TRANSITIONS


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOC_PATH = _REPO_ROOT / "SESSION_LIFECYCLE.md"


def _read_doc() -> str:
    assert _DOC_PATH.exists(), (
        f"missing {_DOC_PATH} — T228 needs the doc written"
    )
    return _DOC_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# State coverage
# ---------------------------------------------------------------------------


def test_doc_mentions_every_session_state() -> None:
    """Every state in the SessionState enum must appear by name
    in the doc — otherwise readers can't look up what each
    state does."""
    doc = _read_doc()
    missing = [s.value for s in SessionState if s.value not in doc]
    assert not missing, (
        f"SESSION_LIFECYCLE.md is missing states: {missing}. "
        f"Add a section per state."
    )


# ---------------------------------------------------------------------------
# Transition coverage
# ---------------------------------------------------------------------------


def test_doc_mentions_every_allowed_transition() -> None:
    """Every (from -> to) edge in the FSM must appear in the
    doc, written either as ``a -> b`` (markdown / ascii) or
    ``a → b`` (unicode arrow). Catches the rot where a new
    transition is added in code but the diagram in prose
    still shows the old graph."""
    doc = _read_doc()
    missing: list[str] = []
    for src, dests in _TRANSITIONS.items():
        for dst in dests:
            patterns = (
                f"{src.value} -> {dst.value}",
                f"{src.value} → {dst.value}",
            )
            if not any(p in doc for p in patterns):
                missing.append(f"{src.value} -> {dst.value}")
    assert not missing, (
        f"SESSION_LIFECYCLE.md is missing transitions:\n  "
        + "\n  ".join(missing)
        + "\nAdd them to the transition diagram or table."
    )


# ---------------------------------------------------------------------------
# Freshness marker
# ---------------------------------------------------------------------------


def test_doc_has_last_reviewed_marker() -> None:
    """Doc must carry an explicit "Last reviewed: YYYY-MM-DD"
    line so future readers can spot a multi-month-stale doc at
    a glance instead of having to diff against git history."""
    doc = _read_doc()
    pattern = r"Last reviewed:\s*\d{4}-\d{2}-\d{2}"
    assert re.search(pattern, doc), (
        "SESSION_LIFECYCLE.md is missing a 'Last reviewed: "
        "YYYY-MM-DD' line. Add one near the top so readers can "
        "judge staleness."
    )
