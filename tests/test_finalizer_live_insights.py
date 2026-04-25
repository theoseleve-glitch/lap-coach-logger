"""T099: Bundle finalizer includes live-generated insights.

When the live session emitted coaching insights via the rules
engine (T080–T083 path), the finalizer must serialise them
into the bundle so the server can:

- See what the client coach told the user during the session.
- Tag them as ``source: "client"`` to weight them lower than
  the server's own post-session insights (server is authoritative
  per ADR-009; client coaching is best-effort latency cover).
- Audit them post-hoc against the canonical bundle (T105 ships
  the per-rule audit).

T099 ships the **writer** + the finalizer wiring. The session-
state plumbing that hands a list of insights to the finalizer
lands later — for now, callers can pass ``live_insights=`` as a
kwarg.

File shape: ``coaching_insights.json`` in the bundle dir, JSON
list with one entry per fired insight:

    [
      {
        "rule_id": "br.late_braking",
        "payload": {"title": "Brake later", "skill_levels": {...}},
        "source": "client"
      }
    ]
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lap_coach_logger.coaching.rules_engine import (
    CoachingInsight,
    write_live_insights,
)
from lap_coach_logger.writers.finalizer import SessionFinalizer
from tests.helpers import make_quality_samples


# ---------------------------------------------------------------------------
# write_live_insights: standalone writer
# ---------------------------------------------------------------------------


def test_write_live_insights_creates_json_file(tmp_path: Path) -> None:
    insights = [
        CoachingInsight(
            rule_id="br.late",
            payload={"title": "Brake later", "category": "braking"},
        ),
        CoachingInsight(
            rule_id="ac.apex_loss",
            payload={"title": "Carry apex speed"},
        ),
    ]

    write_live_insights(tmp_path, insights=insights)

    target = tmp_path / "coaching_insights.json"
    assert target.exists()


def test_written_insights_have_client_source_tag(tmp_path: Path) -> None:
    """Per ADR-009: server-side insights are authoritative;
    client-side ones are best-effort coaching during the session.
    The ``source: "client"`` tag lets the server weight them
    appropriately during reconciliation."""
    insights = [
        CoachingInsight(
            rule_id="br.late",
            payload={"title": "Brake later"},
        )
    ]

    write_live_insights(tmp_path, insights=insights)

    written = json.loads(
        (tmp_path / "coaching_insights.json").read_text(encoding="utf-8")
    )
    assert all(entry["source"] == "client" for entry in written)


def test_written_insights_preserve_rule_id_and_payload(tmp_path: Path) -> None:
    """The audit path (T105) needs both rule_id (which rule
    fired) and full payload (which variant was shown). Lossy
    serialisation would mean the server can't distinguish a
    refactored rule from a renamed one."""
    payload = {
        "title": "Brake later",
        "rationale": "you're scrubbing speed at T1",
        "skill_levels": {"intermediate": "Trail to apex."},
    }
    insights = [CoachingInsight(rule_id="br.late", payload=payload)]

    write_live_insights(tmp_path, insights=insights)

    written = json.loads(
        (tmp_path / "coaching_insights.json").read_text(encoding="utf-8")
    )
    assert written[0]["rule_id"] == "br.late"
    assert written[0]["payload"] == payload


def test_write_live_insights_with_empty_list_writes_empty_array(
    tmp_path: Path,
) -> None:
    """A session that fired no rules still produces the file —
    just empty. Lets the server distinguish "client coaching off
    / no rules fired" from "client coaching crashed mid-session"
    without inferring from file presence."""
    write_live_insights(tmp_path, insights=[])

    written = json.loads(
        (tmp_path / "coaching_insights.json").read_text(encoding="utf-8")
    )
    assert written == []


# ---------------------------------------------------------------------------
# Finalizer integration
# ---------------------------------------------------------------------------


def test_finalizer_writes_coaching_insights_when_provided(
    tmp_path: Path,
) -> None:
    """End-to-end: caller hands ``live_insights=`` to the
    finalizer; the bundle contains ``coaching_insights.json``."""
    fin = SessionFinalizer(tmp_path)
    started_at = datetime(2026, 4, 25, tzinfo=timezone.utc)
    insights = [CoachingInsight(rule_id="br.late", payload={"title": "Brake later"})]

    bundle_dir = fin.finalize(
        make_quality_samples(),
        started_at=started_at,
        ended_at=started_at + timedelta(seconds=120),
        sim="iRacing",
        track="Spa",
        session_type="Race",
        session_uid="t099",
        extra_metadata={"car": "BMW M4 GT3", "sample_rate_hz": 1.0},
        live_insights=insights,
    )

    assert bundle_dir is not None
    assert (bundle_dir / "coaching_insights.json").exists()


def test_finalizer_skips_coaching_insights_file_when_none_provided(
    tmp_path: Path,
) -> None:
    """``live_insights=None`` means "this caller doesn't use the
    rules engine" (e.g., demo mode). Don't write an empty file
    — the server treats absence as "not configured", presence
    as "configured but possibly empty"."""
    fin = SessionFinalizer(tmp_path)
    started_at = datetime(2026, 4, 25, tzinfo=timezone.utc)

    bundle_dir = fin.finalize(
        make_quality_samples(),
        started_at=started_at,
        ended_at=started_at + timedelta(seconds=120),
        sim="iRacing",
        track="Spa",
        session_type="Race",
        session_uid="t099-none",
        extra_metadata={"car": "BMW M4 GT3", "sample_rate_hz": 1.0},
        # live_insights omitted
    )

    assert bundle_dir is not None
    assert not (bundle_dir / "coaching_insights.json").exists()


def test_finalizer_writes_empty_array_when_explicitly_empty(
    tmp_path: Path,
) -> None:
    """Caller explicitly passes an empty list: rules engine WAS
    configured, just nothing fired. Write the empty file so the
    server's audit path doesn't conflate "off" with "ran clean"."""
    fin = SessionFinalizer(tmp_path)
    started_at = datetime(2026, 4, 25, tzinfo=timezone.utc)

    bundle_dir = fin.finalize(
        make_quality_samples(),
        started_at=started_at,
        ended_at=started_at + timedelta(seconds=120),
        sim="iRacing",
        track="Spa",
        session_type="Race",
        session_uid="t099-empty",
        extra_metadata={"car": "BMW M4 GT3", "sample_rate_hz": 1.0},
        live_insights=[],
    )

    assert bundle_dir is not None
    assert (bundle_dir / "coaching_insights.json").exists()
    written = json.loads(
        (bundle_dir / "coaching_insights.json").read_text(encoding="utf-8")
    )
    assert written == []
