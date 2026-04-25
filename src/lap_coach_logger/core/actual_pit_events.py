"""T145: Actual pit events captured during the race.

Per Q102 the bundle ships pre-race plan + actual pit events +
execution delta. T144 covered the plan; T146 will compute the
delta. T145 ships the *actuals* — the data structure plus
record API that future sim-detection wiring (T140's pit-call
state machine) and a user-annotation slot can both feed.

:class:`ActualPitEvent` is a frozen dataclass so the log can
hash + share instances without defensive copies (same rule as
T121's :class:`WidgetPlacement`). :class:`ActualPitEventLog`
keeps events in append order and rejects out-of-order writes
— wall-clock time only goes forward, so a pit at lap 10 after
one at lap 25 is a caller bug, not a valid edge case.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Valid sources for an :class:`ActualPitEvent`. ``sim_detected``
# entries come from the pit-call state machine catching the
# car entering / exiting pit lane. ``user_annotated`` entries
# come from a button on the strategy widget — used in series
# where the sim doesn't surface pit_in / pit_out cleanly.
_VALID_SOURCES: frozenset[str] = frozenset({
    "sim_detected",
    "user_annotated",
})


@dataclass(frozen=True, slots=True)
class ActualPitEvent:
    """A single pit stop the driver actually executed.

    Fields beyond ``lap`` / ``timestamp_utc`` / ``source`` are
    optional because not every sim adapter (or user
    annotation flow) surfaces them — None means 'unknown',
    which is distinct from a real zero.
    """

    lap: int
    timestamp_utc: str
    source: str
    fuel_added_l: float | None = None
    tire_compound: str | None = None
    duration_s: float | None = None

    def __post_init__(self) -> None:
        if self.source not in _VALID_SOURCES:
            raise ValueError(
                f"invalid source {self.source!r} — must be one of "
                f"{sorted(_VALID_SOURCES)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "lap": self.lap,
            "timestamp_utc": self.timestamp_utc,
            "source": self.source,
            "fuel_added_l": self.fuel_added_l,
            "tire_compound": self.tire_compound,
            "duration_s": self.duration_s,
        }


class ActualPitEventLog:
    """Append-only log of :class:`ActualPitEvent`.

    Caller drives chronologically; :meth:`record` rejects an
    event whose lap is *strictly less than* the most recent
    entry. Equal-lap is allowed because the chequered flag can
    pass mid-pit (final pit + final lap share a number).
    """

    def __init__(self) -> None:
        self._events: list[ActualPitEvent] = []

    @property
    def events(self) -> tuple[ActualPitEvent, ...]:
        """Snapshot of recorded events in append order."""
        return tuple(self._events)

    def record(self, event: ActualPitEvent) -> None:
        """Append ``event`` to the log.

        Raises :class:`ValueError` if ``event.lap`` is strictly
        less than the most recent entry's lap — a caller bug
        (wall-clock time only goes forward). Equal laps are
        accepted (chequered-during-pit edge case).
        """
        if self._events and event.lap < self._events[-1].lap:
            raise ValueError(
                f"event lap {event.lap} is out of order "
                f"(last recorded lap was {self._events[-1].lap})"
            )
        self._events.append(event)

    def to_list(self) -> list[dict[str, Any]]:
        """JSON-friendly serialisation — list of per-event
        dicts in chronological order. Bundle writer
        (T146 integration) consumes this directly."""
        return [event.to_dict() for event in self._events]


__all__ = ["ActualPitEvent", "ActualPitEventLog"]
