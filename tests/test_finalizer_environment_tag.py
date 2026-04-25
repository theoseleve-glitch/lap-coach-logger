"""T115: Finalized session bundle carries ``environment_tag``.

Per Q96 / T106's :class:`Mode` ABC, every active mode exposes
an ``environment_tag`` (e.g. ``"sim_practice"`` /
``"sim_sprint"`` / ``"sim_endurance"`` / ``"sim_review"``) that
the **server uses for cohort aggregation** — it's how a fleet
of sessions gets bucketed into "competitive sprint", "endurance
race", etc., independently of the desktop's UI mode label.

T115 wires the active mode's ``environment_tag`` into the
finalized bundle so the server can read it from the canonical
``session.json`` v2 manifest at ingest time. The mode engine
itself isn't yet plugged into the finalize call site (T118+
ships that integration); T115 only ensures the *bundle
contract* exposes the tag — callers who already know the
mode (e.g. Q108 demo mode) can set it today, and the live
processor wiring lands later without a manifest schema change.

The tag lives under ``session.environment_tag`` in
session.json v2 — the same block that already carries
``session.mode``, ``session.driver_name``, etc. Empty string
is the explicit "unset" sentinel (matches existing pattern
for ``raw_car`` / ``raw_track`` / ``driver_name`` when callers
don't supply them — see write_bundle_v2 line 51-56).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lap_coach_logger.writers.finalizer import SessionFinalizer
from tests.helpers import make_quality_samples


# ---------------------------------------------------------------------------
# Finalizer threads environment_tag into session.json
# ---------------------------------------------------------------------------


def _finalize_with_tag(
    tmp_path: Path, *, tag: str | None, uid: str
) -> Path:
    fin = SessionFinalizer(tmp_path)
    started_at = datetime(2026, 4, 25, tzinfo=timezone.utc)
    kwargs: dict = {
        "started_at": started_at,
        "ended_at": started_at + timedelta(seconds=120),
        "sim": "iRacing",
        "track": "Spa",
        "session_type": "Race",
        "session_uid": uid,
        "extra_metadata": {"car": "BMW M4 GT3", "sample_rate_hz": 1.0},
    }
    if tag is not None:
        kwargs["environment_tag"] = tag
    bundle_dir = fin.finalize(make_quality_samples(), **kwargs)
    assert bundle_dir is not None
    return bundle_dir


def _read_session_v2(bundle_dir: Path) -> dict:
    return json.loads((bundle_dir / "session.json").read_text(encoding="utf-8"))


def test_finalizer_threads_environment_tag_into_session_json(
    tmp_path: Path,
) -> None:
    """Caller passes ``environment_tag="sim_endurance"`` (the
    Endurance mode's tag per T109). The bundle's session.json
    must echo it under ``session.environment_tag``. This is what
    the server reads to bucket the session for cohort analysis."""
    bundle_dir = _finalize_with_tag(
        tmp_path, tag="sim_endurance", uid="t115-endurance"
    )

    session_json = _read_session_v2(bundle_dir)

    assert session_json["session"]["environment_tag"] == "sim_endurance"


def test_finalizer_defaults_environment_tag_to_empty_string_when_omitted(
    tmp_path: Path,
) -> None:
    """Pre-T115 callers don't pass ``environment_tag``. The
    bundle must still validate — empty string is the explicit
    "unset" sentinel matching the convention used for unset
    ``raw_car`` / ``raw_track`` / ``driver_name`` in v2.

    The server treats empty as "untagged, fall back to
    session_type" rather than rejecting the bundle, so existing
    capture paths keep working until T118 wires the mode engine
    in everywhere."""
    bundle_dir = _finalize_with_tag(tmp_path, tag=None, uid="t115-default")

    session_json = _read_session_v2(bundle_dir)

    assert session_json["session"]["environment_tag"] == ""


def test_finalizer_round_trips_all_four_canonical_mode_tags(
    tmp_path: Path,
) -> None:
    """Sweep all four mode tags (T107-T110). Catches a refactor
    that would, say, accidentally lower-case or strip the
    ``sim_`` prefix on the way through the writer chain — would
    break server-side cohort routing silently."""
    expected_tags = [
        "sim_practice",
        "sim_sprint",
        "sim_endurance",
        "sim_review",
    ]

    seen: list[str] = []
    for i, tag in enumerate(expected_tags):
        sub = tmp_path / f"run_{i}"
        sub.mkdir()
        bundle_dir = _finalize_with_tag(
            sub, tag=tag, uid=f"t115-roundtrip-{i}"
        )
        seen.append(_read_session_v2(bundle_dir)["session"]["environment_tag"])

    assert seen == expected_tags
