"""T145: Actual pit events captured + stored.

Per Q102 the post-session bundle must carry the *actual* pit
events alongside T144's pre-race plan so T146 can compute the
plan-vs-actual delta. T145 ships the capture + store layer:

- :class:`ActualPitEvent` — frozen dataclass, one record per
  pit stop the driver actually executed.
- :class:`ActualPitEventLog` — append-only log keeping events
  in chronological lap order. Rejects out-of-order writes
  (no time travel), exposes a list-of-dicts serialiser for the
  bundle.
- ``source`` field tags whether the entry came from sim
  detection (T140's pit-call state machine) or user annotation
  (a button on the strategy widget for series where the sim
  doesn't surface pit_in/pit_out events cleanly).

Out of scope for T145: the wiring from sim/user input *into*
the log, and the serialisation into the v2 bundle. Those are
T144's bundle layer + later integration. T145 is the data
structure that makes both possible.
"""
from __future__ import annotations

import pytest

from lap_coach_logger.core.actual_pit_events import (
    ActualPitEvent,
    ActualPitEventLog,
)


# ---------------------------------------------------------------------------
# ActualPitEvent dataclass
# ---------------------------------------------------------------------------


def test_actual_pit_event_holds_lap_and_source() -> None:
    """Minimal event has at least lap + timestamp + source.
    Pin the headline fields so a future schema tweak that
    drops one of them gets caught here."""
    event = ActualPitEvent(
        lap=21,
        timestamp_utc="2026-04-25T13:01:00Z",
        source="sim_detected",
    )

    assert event.lap == 21
    assert event.timestamp_utc == "2026-04-25T13:01:00Z"
    assert event.source == "sim_detected"


def test_actual_pit_event_is_frozen() -> None:
    """Immutable so the log can hash + share instances. Same
    rationale as :class:`WidgetPlacement` (T121)."""
    from dataclasses import FrozenInstanceError

    event = ActualPitEvent(
        lap=21, timestamp_utc="x", source="sim_detected",
    )

    with pytest.raises(FrozenInstanceError):
        event.lap = 99  # type: ignore[misc]


def test_actual_pit_event_optional_fields_default_to_none() -> None:
    """fuel_added_l / tire_compound / duration_s are optional
    — sim adapters that don't surface them cleanly leave them
    as None rather than fabricating zeros (which would mask
    'unknown' as 'no fuel added')."""
    event = ActualPitEvent(
        lap=21, timestamp_utc="x", source="sim_detected",
    )

    assert event.fuel_added_l is None
    assert event.tire_compound is None
    assert event.duration_s is None


def test_actual_pit_event_optional_fields_round_trip() -> None:
    """When the sim does provide fuel + tires + duration, the
    fields ride along on the dataclass."""
    event = ActualPitEvent(
        lap=21, timestamp_utc="x", source="sim_detected",
        fuel_added_l=46.5, tire_compound="medium", duration_s=24.7,
    )

    assert event.fuel_added_l == 46.5
    assert event.tire_compound == "medium"
    assert event.duration_s == 24.7


# ---------------------------------------------------------------------------
# Source tag: sim_detected vs user_annotated
# ---------------------------------------------------------------------------


def test_source_must_be_sim_detected_or_user_annotated() -> None:
    """T146's plan-vs-actual logic might want to weight sim-
    detected events higher than user-annotated (different
    confidence). Pin the two valid tags so a typo at a call
    site fails loudly at construction."""
    ActualPitEvent(lap=1, timestamp_utc="x", source="sim_detected")
    ActualPitEvent(lap=1, timestamp_utc="x", source="user_annotated")

    with pytest.raises(ValueError, match="source"):
        ActualPitEvent(lap=1, timestamp_utc="x", source="bogus")


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def test_event_to_dict_shape() -> None:
    """Bundle is JSON. The dict shape must include every
    field; None values surface as JSON null after json.dumps —
    no defensive filtering."""
    event = ActualPitEvent(
        lap=21, timestamp_utc="2026-04-25T13:01:00Z",
        source="sim_detected",
        fuel_added_l=46.5, tire_compound="medium", duration_s=24.7,
    )

    assert event.to_dict() == {
        "lap": 21,
        "timestamp_utc": "2026-04-25T13:01:00Z",
        "source": "sim_detected",
        "fuel_added_l": 46.5,
        "tire_compound": "medium",
        "duration_s": 24.7,
    }


# ---------------------------------------------------------------------------
# ActualPitEventLog: store + ordering
# ---------------------------------------------------------------------------


def test_empty_log_has_no_events() -> None:
    """Default state is empty so ``to_list()`` of a session
    with no pit stops produces ``[]`` — webapp can render
    'no pits' from an empty list."""
    log = ActualPitEventLog()

    assert log.events == ()
    assert log.to_list() == []


def test_record_appends_event() -> None:
    """Single record path."""
    log = ActualPitEventLog()
    event = ActualPitEvent(
        lap=21, timestamp_utc="x", source="sim_detected",
    )

    log.record(event)

    assert log.events == (event,)


def test_records_preserve_chronological_order() -> None:
    """Iteration order is the order of recording (which the
    caller drives chronologically). Pin so a refactor to a
    set / dict keyed by lap can't silently shuffle."""
    log = ActualPitEventLog()
    first = ActualPitEvent(lap=10, timestamp_utc="t1", source="sim_detected")
    second = ActualPitEvent(lap=25, timestamp_utc="t2", source="sim_detected")
    third = ActualPitEvent(lap=40, timestamp_utc="t3", source="user_annotated")

    log.record(first)
    log.record(second)
    log.record(third)

    assert log.events == (first, second, third)


def test_record_rejects_out_of_order_lap() -> None:
    """A pit at lap 25 followed by one at lap 10 is a caller
    bug — wall-clock time only goes forward. Reject so the
    delta calculation later (T146) sees a well-ordered
    sequence."""
    log = ActualPitEventLog()
    log.record(ActualPitEvent(
        lap=25, timestamp_utc="t1", source="sim_detected",
    ))

    with pytest.raises(ValueError, match="out of order"):
        log.record(ActualPitEvent(
            lap=10, timestamp_utc="t2", source="user_annotated",
        ))


def test_record_allows_same_lap_event() -> None:
    """The chequered flag passes mid-pit — final pit and the
    final lap can share a number. Don't reject equal-lap
    entries."""
    log = ActualPitEventLog()
    log.record(ActualPitEvent(
        lap=25, timestamp_utc="t1", source="sim_detected",
    ))

    # Same lap — must not raise
    log.record(ActualPitEvent(
        lap=25, timestamp_utc="t2", source="user_annotated",
    ))

    assert len(log.events) == 2


# ---------------------------------------------------------------------------
# to_list serialisation walks the events
# ---------------------------------------------------------------------------


def test_log_to_list_serialises_each_event() -> None:
    """Bundle path: log.to_list() is the JSON-friendly
    representation. Each event's to_dict appears in
    chronological order."""
    log = ActualPitEventLog()
    log.record(ActualPitEvent(
        lap=10, timestamp_utc="t1", source="sim_detected", fuel_added_l=40.0,
    ))
    log.record(ActualPitEvent(
        lap=25, timestamp_utc="t2", source="user_annotated",
    ))

    payload = log.to_list()

    assert payload == [
        {
            "lap": 10, "timestamp_utc": "t1", "source": "sim_detected",
            "fuel_added_l": 40.0, "tire_compound": None, "duration_s": None,
        },
        {
            "lap": 25, "timestamp_utc": "t2", "source": "user_annotated",
            "fuel_added_l": None, "tire_compound": None, "duration_s": None,
        },
    ]


# ---------------------------------------------------------------------------
# JSON round-trip (the bundle is JSON, so non-JSON-friendly types break it)
# ---------------------------------------------------------------------------


def test_log_to_list_is_json_friendly() -> None:
    """Same defensive pin as T144's serializer — non-JSON-able
    payload here would silently break finalisation. Catch it
    in the unit test."""
    import json

    log = ActualPitEventLog()
    log.record(ActualPitEvent(
        lap=21, timestamp_utc="2026-04-25T13:01:00Z",
        source="sim_detected", fuel_added_l=46.5,
    ))

    serialised = json.dumps(log.to_list())
    rehydrated = json.loads(serialised)

    assert rehydrated == log.to_list()
