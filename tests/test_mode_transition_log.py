"""T119: Mid-recording mode switch is allowed-but-logged.

Switching mode while a session is being captured is *not*
blocked (per T119 spec — "allowed"), but it has to leave a
trace so post-session analysis can split the bundle's mode
tag at the right offset. Two artefacts:

1. A ``SessionEvent(event="mode_changed", detail={"from", "to"})``
   that gets stitched into the events stream — the bundle's
   ``events.json`` then carries the split timestamp so server-
   side aggregation can bucket pre/post-switch laps separately.

2. An INFO log line so ops can see when users flip mid-session
   without trawling event files. Pattern matches existing
   detection-log outputs (`mode_detector` etc.).

T119 ships the *helper*: a pure function that builds the
event from (from_mode, to_mode) plus an injectable ``now``
clock. Recording-side wiring (subscribing the recorder to
``ModeEngine.on_mode_changed`` and shipping the event into
the live events buffer) lands at T120 E2E — same shape as the
T112/T113/T114 binding adapters.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from lap_coach_logger.writers.bundle_schema import SessionEvent


# ---------------------------------------------------------------------------
# Event builder shape
# ---------------------------------------------------------------------------


def test_builder_returns_a_session_event() -> None:
    from lap_coach_logger.core.modes.transition_log import (
        build_mode_transition_event,
    )

    event = build_mode_transition_event("sprint", "endurance")

    assert isinstance(event, SessionEvent)


def test_event_kind_is_mode_changed() -> None:
    """The event kind has to be a stable string the server's
    bundle reader can pattern-match on. ``mode_changed``
    matches the convention ModeViewModel + analytics already use
    (T063 emits ``mode_switched`` to PostHog — same idea, but
    kept distinct so events.json doesn't collide with
    PostHog naming if both ever round-trip through the same
    log)."""
    from lap_coach_logger.core.modes.transition_log import (
        build_mode_transition_event,
    )

    event = build_mode_transition_event("sprint", "endurance")

    assert event.event == "mode_changed"


def test_event_detail_carries_from_and_to_mode_ids() -> None:
    """Server's split-the-bundle path needs both ``from`` and
    ``to`` so it can attribute laps to the right mode bucket.
    A single ``mode`` field would force the server to
    reconstruct the previous mode by walking back through prior
    events."""
    from lap_coach_logger.core.modes.transition_log import (
        build_mode_transition_event,
    )

    event = build_mode_transition_event("sprint", "endurance")

    assert event.detail == {"from": "sprint", "to": "endurance"}


# ---------------------------------------------------------------------------
# Timestamp comes from injectable clock
# ---------------------------------------------------------------------------


def test_event_uses_injected_now_in_iso8601_utc() -> None:
    """Tests inject a fixed ``now`` so the timestamp is
    deterministic; production passes ``datetime.now(timezone.utc)``.
    The string format matches the rest of the bundle (ISO 8601
    UTC with ``+00:00`` suffix) so events.json round-trips
    cleanly through ``datetime.fromisoformat``."""
    from lap_coach_logger.core.modes.transition_log import (
        build_mode_transition_event,
    )

    fixed_now = datetime(2026, 4, 25, 14, 30, 0, tzinfo=timezone.utc)

    event = build_mode_transition_event(
        "sprint", "endurance", now=fixed_now
    )

    assert event.timestamp_utc == "2026-04-25T14:30:00+00:00"


def test_default_now_returns_current_utc_time() -> None:
    """No ``now=`` ⇒ stamp with the current UTC time. Loose
    bound (event timestamp ≥ pre-call timestamp) since wall-
    clock is non-deterministic; just pinning the contract that
    the default isn't a frozen sentinel."""
    from lap_coach_logger.core.modes.transition_log import (
        build_mode_transition_event,
    )

    before = datetime.now(timezone.utc)
    event = build_mode_transition_event("sprint", "endurance")
    after = datetime.now(timezone.utc)

    parsed = datetime.fromisoformat(event.timestamp_utc)
    assert before <= parsed <= after


# ---------------------------------------------------------------------------
# Logging side-effect
# ---------------------------------------------------------------------------


def test_builder_logs_an_info_line(caplog) -> None:
    """Ops needs visibility into mid-session mode switches
    without parsing every events.json. Match the pattern
    ``mode_detector`` already uses — INFO level, structured
    enough to grep for both modes."""
    from lap_coach_logger.core.modes.transition_log import (
        build_mode_transition_event,
    )

    with caplog.at_level(logging.INFO, logger="lap_coach_logger.core.modes.transition_log"):
        build_mode_transition_event("sprint", "endurance")

    # At least one INFO record from this module mentioning both modes.
    relevant = [
        r for r in caplog.records
        if r.name == "lap_coach_logger.core.modes.transition_log"
        and r.levelno == logging.INFO
    ]
    assert relevant, "expected one INFO log record on mode transition"
    text = relevant[0].getMessage().lower()
    assert "sprint" in text
    assert "endurance" in text


# ---------------------------------------------------------------------------
# No-op same-mode transitions still produce an event
# ---------------------------------------------------------------------------


def test_same_from_and_to_still_builds_event() -> None:
    """The *engine* no-ops on re-selecting the active mode
    (T111). T119's helper is a pure builder — it doesn't know
    about engine state, so callers can build any (from, to)
    pair. The dedup is the engine's responsibility, not the
    log helper's. Keeping this layer dumb makes it reusable
    by tooling that *wants* to record self-loops (e.g.,
    diagnostic dumps)."""
    from lap_coach_logger.core.modes.transition_log import (
        build_mode_transition_event,
    )

    event = build_mode_transition_event("sprint", "sprint")

    assert event.detail == {"from": "sprint", "to": "sprint"}
