"""T144: serialise a :class:`RaceStrategy` for the v2 bundle.

Per Q102 the post-session bundle carries the pre-race plan so
the webapp review can render plan-vs-actual. T144 ships the
*plan* slice — the dataclass conversion only.

Schema is deliberately flat (no envelope). The bundle as a
whole already carries ``schema_version: 2``; nesting another
version inside :data:`race_strategy` would be redundant. Webapp
readers can pluck fields directly from
``manifest["race_strategy"]``.
"""
from __future__ import annotations

from typing import Any

from lap_coach_logger.core.race_strategy import PitStop, RaceStrategy


def _serialize_pit_stop(stop: PitStop) -> dict[str, Any]:
    return {
        "lap": stop.lap,
        "fuel_to_add": stop.fuel_to_add,
        "tire_compound": stop.tire_compound,
        "estimated_time_s": stop.estimated_time_s,
    }


def serialize_race_strategy(strategy: RaceStrategy) -> dict[str, Any]:
    """Convert a :class:`RaceStrategy` into a JSON-friendly dict.

    Output shape (flat):

    - ``total_laps``, ``fuel_capacity``, ``fuel_per_lap``,
      ``tire_life_laps`` — race scope
    - ``total_race_time_s``, ``fuel_at_finish`` — derived totals
    - ``pit_stops`` — list of :func:`_serialize_pit_stop` dicts
    """
    return {
        "total_laps": strategy.total_laps,
        "fuel_capacity": strategy.fuel_capacity,
        "fuel_per_lap": strategy.fuel_per_lap,
        "tire_life_laps": strategy.tire_life_laps,
        "total_race_time_s": strategy.total_race_time_s,
        "fuel_at_finish": strategy.fuel_at_finish,
        "pit_stops": [_serialize_pit_stop(s) for s in strategy.pit_stops],
    }


__all__ = ["serialize_race_strategy"]
