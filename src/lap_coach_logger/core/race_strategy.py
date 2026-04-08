"""Race strategy engine -- pit stop planning and live recalculation.

Calculates optimal pit strategy based on fuel capacity, consumption,
tire degradation windows, and pit lane time.  Supports both pre-race
planning and live mid-race recalculation from actual telemetry data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class PitStop:
    """A single planned pit stop."""

    lap: int
    fuel_to_add: float  # liters
    tire_compound: str  # "soft" / "medium" / "hard" / "wet"
    estimated_time_s: float  # pit lane time loss


@dataclass
class RaceStrategy:
    """Complete race strategy with pit stops and estimates."""

    total_laps: int
    fuel_capacity: float
    fuel_per_lap: float
    tire_life_laps: int  # estimated degradation window
    pit_stops: list[PitStop] = field(default_factory=list)
    total_race_time_s: float = 0.0
    fuel_at_finish: float = 0.0

    @property
    def num_stops(self) -> int:
        return len(self.pit_stops)


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------


def calculate_strategy(
    total_laps: int,
    fuel_capacity: float,
    fuel_per_lap: float,
    tire_life_laps: int = 999,
    pit_time_s: float = 25.0,
    current_lap: int = 0,
    current_fuel: float = 0.0,
    lap_time_s: float = 90.0,
) -> RaceStrategy:
    """Calculate optimal pit strategy.

    Logic:
    1. Calculate fuel stint: how many laps per full tank.
    2. Calculate tire stint: how many laps before tires degrade.
    3. Effective stint = min(fuel_stint, tire_stint).
    4. Distribute pit stops evenly across the remaining race.
    5. Calculate fuel to add at each stop (fill to cover next stint + margin).
    """
    if total_laps <= 0 or fuel_per_lap <= 0:
        return RaceStrategy(
            total_laps=max(0, total_laps),
            fuel_capacity=fuel_capacity,
            fuel_per_lap=fuel_per_lap,
            tire_life_laps=tire_life_laps,
        )

    remaining_laps = total_laps - current_lap
    if remaining_laps <= 0:
        return RaceStrategy(
            total_laps=total_laps,
            fuel_capacity=fuel_capacity,
            fuel_per_lap=fuel_per_lap,
            tire_life_laps=tire_life_laps,
        )

    # How many laps a full tank can cover
    fuel_stint = max(1, int(fuel_capacity / fuel_per_lap))
    # Effective stint (limited by tire life)
    effective_stint = min(fuel_stint, tire_life_laps)

    # Starting fuel: full tank if pre-race, current_fuel if mid-race
    start_fuel = current_fuel if current_fuel > 0 else fuel_capacity

    # How many laps the starting fuel covers
    first_stint_laps = min(int(start_fuel / fuel_per_lap), effective_stint)
    first_stint_laps = max(1, first_stint_laps)

    # Calculate number of stops needed
    if first_stint_laps >= remaining_laps:
        # No pit stop needed
        fuel_at_finish = start_fuel - (remaining_laps * fuel_per_lap)
        total_time = remaining_laps * lap_time_s
        return RaceStrategy(
            total_laps=total_laps,
            fuel_capacity=fuel_capacity,
            fuel_per_lap=fuel_per_lap,
            tire_life_laps=tire_life_laps,
            pit_stops=[],
            total_race_time_s=total_time,
            fuel_at_finish=round(fuel_at_finish, 2),
        )

    # Laps remaining after first stint
    laps_after_first = remaining_laps - first_stint_laps
    num_stops = max(1, math.ceil(laps_after_first / effective_stint))

    # Distribute stops evenly
    pit_stops: list[PitStop] = []
    laps_covered = current_lap + first_stint_laps

    for i in range(num_stops):
        # How many laps until next stop (or end)
        laps_left_after_stop = total_laps - laps_covered
        if i < num_stops - 1:
            # Even split of remaining laps among remaining stints
            remaining_stints = num_stops - i
            next_stint = min(
                effective_stint,
                math.ceil(laps_left_after_stop / remaining_stints),
            )
        else:
            # Last stop: cover remaining laps
            next_stint = laps_left_after_stop

        next_stint = max(1, next_stint)

        # Fuel to add: enough for the next stint plus a small margin (0.5 lap)
        fuel_needed = (next_stint + 0.5) * fuel_per_lap
        fuel_to_add = min(fuel_needed, fuel_capacity)
        fuel_to_add = round(fuel_to_add, 1)

        pit_stops.append(PitStop(
            lap=laps_covered,
            fuel_to_add=fuel_to_add,
            tire_compound="medium",
            estimated_time_s=pit_time_s,
        ))

        laps_covered += next_stint

    # Total race time estimate
    total_time = (remaining_laps * lap_time_s) + (num_stops * pit_time_s)

    # Fuel at finish: approximate from last stint
    if pit_stops:
        last_stop = pit_stops[-1]
        laps_in_last_stint = total_laps - last_stop.lap
        fuel_at_finish = last_stop.fuel_to_add - (laps_in_last_stint * fuel_per_lap)
    else:
        fuel_at_finish = start_fuel - (remaining_laps * fuel_per_lap)

    return RaceStrategy(
        total_laps=total_laps,
        fuel_capacity=fuel_capacity,
        fuel_per_lap=fuel_per_lap,
        tire_life_laps=tire_life_laps,
        pit_stops=pit_stops,
        total_race_time_s=round(total_time, 1),
        fuel_at_finish=round(fuel_at_finish, 2),
    )


def recalculate_live(
    strategy: RaceStrategy,
    current_lap: int,
    current_fuel: float,
    actual_fuel_per_lap: float,
    laps_remaining: int,
) -> RaceStrategy:
    """Recalculate strategy based on actual race data.

    Rebuilds from current position using actual consumption rate.
    """
    if laps_remaining <= 0 or actual_fuel_per_lap <= 0:
        return RaceStrategy(
            total_laps=strategy.total_laps,
            fuel_capacity=strategy.fuel_capacity,
            fuel_per_lap=actual_fuel_per_lap,
            tire_life_laps=strategy.tire_life_laps,
        )

    total_laps = current_lap + laps_remaining

    return calculate_strategy(
        total_laps=total_laps,
        fuel_capacity=strategy.fuel_capacity,
        fuel_per_lap=actual_fuel_per_lap,
        tire_life_laps=strategy.tire_life_laps,
        pit_time_s=strategy.pit_stops[0].estimated_time_s if strategy.pit_stops else 25.0,
        current_lap=current_lap,
        current_fuel=current_fuel,
        lap_time_s=(
            strategy.total_race_time_s / strategy.total_laps
            if strategy.total_laps > 0
            else 90.0
        ),
    )
