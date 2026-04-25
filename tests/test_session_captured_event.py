"""T061: ``SessionFinalizer.finalize()`` fires the ``session_captured``
PostHog event with sim / track / car / session_type / duration_s
properties.

The natural callpoint is **right after the atomic rename succeeds**
in finalize(): a bundle becomes durable on disk only at that
moment, so any earlier emission would attribute events to sessions
that never actually got saved (e.g. a crash mid-write). On the
exception path finalize() returns ``None`` and we must NOT fire
the event.

Tests record what reaches ``analytics.track`` by monkeypatching
the function — no real PostHog network traffic.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import finalize_session


@pytest.fixture
def track_recorder(monkeypatch: pytest.MonkeyPatch):
    """Replace ``analytics.track`` with a list-recorder for the test."""
    from lap_coach_logger import analytics

    calls: list[tuple[str, dict]] = []

    def _record(event_name: str, **properties: object) -> None:
        calls.append((event_name, properties))

    monkeypatch.setattr(analytics, "track", _record)
    return calls


def test_successful_finalize_fires_session_captured_event(
    tmp_path: Path,
    track_recorder: list[tuple[str, dict]],
) -> None:
    finalize_session(
        tmp_path / "out",
        sim="iRacing",
        track="Spa",
        car="GT3",
        session_type="Race",
        session_uid="t061-success",
    )

    captured = [c for c in track_recorder if c[0] == "session_captured"]
    assert len(captured) == 1
    props = captured[0][1]
    assert props["sim"] == "iRacing"
    assert props["track"] == "Spa"
    assert props["car"] == "GT3"
    assert props["session_type"] == "Race"


def test_session_captured_event_includes_duration_seconds(
    tmp_path: Path,
    track_recorder: list[tuple[str, dict]],
) -> None:
    """Duration is the most actionable funnel property for PostHog —
    it lets us segment 'sessions that completed' from 'sessions that
    started but never finished'."""
    finalize_session(
        tmp_path / "out",
        sim="ACC",
        track="Imola",
        car="Porsche 911 GT3 R",
        session_type="Practice",
        session_uid="t061-duration",
        duration_s=345.0,
    )

    captured = [c for c in track_recorder if c[0] == "session_captured"]
    assert captured[0][1]["duration_s"] == pytest.approx(345.0)


def test_session_captured_event_does_not_carry_pii(
    tmp_path: Path,
    track_recorder: list[tuple[str, dict]],
) -> None:
    """The session_uid is internal — it's used as Idempotency-Key
    when uploading and does not belong in product analytics. Same
    for any path under output_root: file paths often leak the user's
    home directory or driver name."""
    finalize_session(
        tmp_path / "out",
        sim="iRacing",
        track="Spa",
        car="GT3",
        session_type="Race",
        session_uid="01900000-0000-7000-8000-00000000aaaa",
    )

    captured = [c for c in track_recorder if c[0] == "session_captured"]
    props = captured[0][1]
    # Session UUID must not leak as an event property.
    for value in props.values():
        if isinstance(value, str):
            assert "01900000-0000-7000-8000-00000000aaaa" not in value
    assert "session_id" not in props
    assert "session_uid" not in props
    assert "output_path" not in props
    assert "bundle_dir" not in props


def test_failed_finalize_does_not_fire_session_captured(
    tmp_path: Path,
    track_recorder: list[tuple[str, dict]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If finalize() returns ``None`` (e.g. write failure), no
    session_captured event must be emitted — funnels would see
    sessions that didn't survive."""
    from lap_coach_logger.writers import finalizer as finalizer_module

    # Force the body to raise so the except branch returns None.
    def _boom(*_a, **_kw):
        raise RuntimeError("simulated write failure")

    monkeypatch.setattr(
        finalizer_module.SessionFinalizer, "_write_telemetry", _boom
    )

    from lap_coach_logger.writers.finalizer import SessionFinalizer
    from datetime import datetime, timezone, timedelta

    fin = SessionFinalizer(tmp_path / "out")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = fin.finalize(
        samples=[],
        started_at=now,
        ended_at=now + timedelta(seconds=10),
        sim="iRacing",
        track="Spa",
        session_type="Race",
        session_uid="t061-fail",
    )

    assert result is None
    assert [c for c in track_recorder if c[0] == "session_captured"] == []


def test_session_captured_event_is_safe_when_analytics_unconfigured(
    tmp_path: Path,
) -> None:
    """If finalize() is called before bootstrap has wired analytics
    (e.g. during integration tests), the emission must be a no-op
    rather than a crash."""
    from lap_coach_logger import analytics

    analytics.reset()  # explicitly UN-configure
    bundle = finalize_session(
        tmp_path / "out", session_uid="t061-noconfigure"
    )
    assert bundle is not None  # finalize must still succeed
