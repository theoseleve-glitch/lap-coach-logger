"""T146: plan-vs-actual delta for the v2 bundle.

Per Q102 the post-session bundle ships pre-race plan + actual
pit events + execution delta. T144 wired the plan; T145 the
actuals; T146 ships the delta.

Pairing strategy is index-based zip: the i-th planned stop
pairs with the i-th actual stop. Both sequences are
chronological (plan in lap order, actuals in record order),
so this matches how a driver thinks about their plan ("first
stop, second stop"). Avoids fuzzy match-window logic that
would invite tunable thresholds and ambiguous results.

Sign convention for deltas: ``actual - planned``. Positive
means later / more than planned; negative means earlier /
less.
"""
from __future__ import annotations

from typing import Any

from lap_coach_logger.core.actual_pit_events import ActualPitEventLog
from lap_coach_logger.core.race_strategy import RaceStrategy


def compute_plan_vs_actual(
    plan: RaceStrategy,
    actuals: ActualPitEventLog,
) -> dict[str, Any]:
    """Return a JSON-friendly summary comparing ``plan`` against
    ``actuals``.

    Output shape::

        {
          "planned_stops": <int>,
          "actual_stops": <int>,
          "stops": [
            {
              "planned_lap": <int|None>,
              "actual_lap": <int|None>,
              "lap_delta": <int|None>,
              "planned_fuel_l": <float|None>,
              "actual_fuel_l": <float|None>,
              "fuel_delta_l": <float|None>,
              "matched": <bool>,
            },
            ...
          ],
        }

    A pair is *matched* when both planned and actual exist for
    the same index. Lap delta is only computed for matched
    pairs; fuel delta requires both sides to be non-None.
    """
    plan_stops = list(plan.pit_stops)
    actual_events = list(actuals.events)
    n = max(len(plan_stops), len(actual_events))

    stops: list[dict[str, Any]] = []
    for i in range(n):
        planned = plan_stops[i] if i < len(plan_stops) else None
        actual = actual_events[i] if i < len(actual_events) else None

        planned_lap = planned.lap if planned else None
        actual_lap = actual.lap if actual else None

        if planned is not None and actual is not None:
            lap_delta: int | None = actual.lap - planned.lap
        else:
            lap_delta = None

        planned_fuel = planned.fuel_to_add if planned else None
        actual_fuel = actual.fuel_added_l if actual else None
        if (
            planned is not None
            and actual is not None
            and actual.fuel_added_l is not None
        ):
            fuel_delta: float | None = actual.fuel_added_l - planned.fuel_to_add
            # Round to 1 decimal to keep JSON tidy and avoid float
            # ghost-precision (e.g., 3.4999999...). 1 decimal matches
            # the precision the planner already rounds fuel_to_add to.
            fuel_delta = round(fuel_delta, 1)
        else:
            fuel_delta = None

        stops.append({
            "planned_lap": planned_lap,
            "actual_lap": actual_lap,
            "lap_delta": lap_delta,
            "planned_fuel_l": planned_fuel,
            "actual_fuel_l": actual_fuel,
            "fuel_delta_l": fuel_delta,
            "matched": planned is not None and actual is not None,
        })

    return {
        "planned_stops": len(plan_stops),
        "actual_stops": len(actual_events),
        "stops": stops,
    }


__all__ = ["compute_plan_vs_actual"]
