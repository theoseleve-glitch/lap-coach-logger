"""Race strategy engine -- pit stop planning and live recalculation.

Calculates optimal pit strategy based on fuel capacity, consumption,
tire degradation windows, and pit lane time.  Supports both pre-race
planning and live mid-race recalculation from actual telemetry data.

Extended with RacePlan optimizer and live recalculation with divergence
alerts for multi-compound strategies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from lap_coach_logger.core.stint_store import CompoundProfile
from lap_coach_logger.core.strategy_models import (
    DegradationModel,
    PitProfile,
    ThermalModel,
    WarmupModel,
)


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
    current_fuel: float | None = None,
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

    # Starting fuel: full tank if pre-race (None), actual value if mid-race
    start_fuel = fuel_capacity if current_fuel is None else current_fuel
    if start_fuel <= 0:
        start_fuel = fuel_capacity

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

    pit_time_s = strategy.pit_stops[0].estimated_time_s if strategy.pit_stops else 25.0
    if strategy.total_laps > 0 and strategy.total_race_time_s > 0:
        estimated_lap_time_s = strategy.total_race_time_s / strategy.total_laps
    else:
        estimated_lap_time_s = 90.0

    return calculate_strategy(
        total_laps=total_laps,
        fuel_capacity=strategy.fuel_capacity,
        fuel_per_lap=actual_fuel_per_lap,
        tire_life_laps=strategy.tire_life_laps,
        pit_time_s=pit_time_s,
        current_lap=current_lap,
        current_fuel=current_fuel,
        lap_time_s=estimated_lap_time_s,
    )


# ---------------------------------------------------------------------------
#  Enhanced strategy dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PlannedStint:
    """A single stint within a RacePlan."""

    compound: str
    start_lap: int
    end_lap: int
    fuel_at_start: float
    fuel_to_add: float  # fuel added at pit stop entering this stint (0 for first)
    grip_at_end: float  # estimated grip fraction at end of stint
    estimated_time_s: float  # driving time for this stint (no pit time)


@dataclass
class StrategyAlert:
    """An advisory or warning raised during strategy calculation."""

    severity: str  # "info" / "warning" / "critical"
    category: str  # "fuel" / "tire" / "weather" / "divergence"
    message: str
    suggested_action: Optional[str] = None


@dataclass
class RacePlan:
    """Optimized race plan with stints and alerts."""

    stints: list[PlannedStint] = field(default_factory=list)
    total_race_time_s: float = 0.0
    fuel_at_finish: float = 0.0
    alerts: list[StrategyAlert] = field(default_factory=list)

    @property
    def num_stops(self) -> int:
        return max(0, len(self.stints) - 1)

    @property
    def next_pit_lap(self) -> Optional[int]:
        """Lap number of the next pit stop (end of first stint)."""
        if len(self.stints) <= 1:
            return None
        return self.stints[0].end_lap


@dataclass
class ConditionWindow:
    """Track conditions for a range of laps."""

    start_lap: int
    end_lap: int
    track_temp_c: float
    precipitation: float  # 0.0 = dry, 1.0 = heavy rain
    track_state: str  # "dry" / "damp" / "wet"
    recommended_compound: str


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------


def _fuel_for_laps(profile: CompoundProfile, n_laps: int) -> float:
    """Sum fuel consumption for *n_laps* using the profile's per-lap curve.

    If the curve is shorter than *n_laps*, ``fuel_per_lap`` is used
    for the remaining laps.
    """
    if n_laps <= 0:
        return 0.0
    total = 0.0
    for i in range(n_laps):
        if i < len(profile.fuel_curve):
            total += profile.fuel_curve[i]
        else:
            total += profile.fuel_per_lap
    return total


def _apply_temp_correction(
    profile: CompoundProfile,
    track_temp_c: float,
) -> CompoundProfile:
    """Return a corrected *profile* using the fitted :class:`ThermalModel`.

    When the profile has a fitted thermal model the lap-time penalty
    predicted at ``track_temp_c`` is added to the average lap time.
    If no model is available the profile is returned unchanged.
    """
    if profile.thermal:
        thermal = ThermalModel.from_dict(profile.thermal)
        if thermal.available:
            penalty_s = thermal.predict_penalty(track_temp_c)
            new_lap_time = profile.avg_lap_time_s + penalty_s
            return CompoundProfile(
                compound=profile.compound,
                fuel_per_lap=profile.fuel_per_lap,
                fuel_curve=list(profile.fuel_curve),
                wear_per_lap=profile.wear_per_lap,
                estimated_life=profile.estimated_life,
                avg_lap_time_s=new_lap_time,
                lap_time_delta_s=profile.lap_time_delta_s + penalty_s,
                avg_track_temp_c=track_temp_c,
                total_laps_logged=profile.total_laps_logged,
                stint_count=profile.stint_count,
                confidence=profile.confidence,
                thermal=profile.thermal,
                warmup=profile.warmup,
                degradation=profile.degradation,
            )
    return profile


def _grip_at_lap(profile: CompoundProfile, stint_lap: int) -> float:
    """Grip multiplier at a given stint-relative lap (0-indexed).

    Derived from ``wear_per_lap``: grip = max(0, 1.0 - wear_per_lap/100 * N).
    """
    return max(0.0, 1.0 - profile.wear_per_lap / 100.0 * stint_lap)


def _effective_stint_life(profile: CompoundProfile) -> int:
    """Return the effective max stint length for *profile*.

    Uses ``max_viable_stint`` from the fitted :class:`DegradationModel`
    when available, otherwise falls back to ``profile.estimated_life``.
    """
    if profile.degradation:
        deg = DegradationModel.from_dict(profile.degradation)
        if deg.available and deg.max_viable_stint is not None:
            return int(deg.max_viable_stint)
    return int(profile.estimated_life)


def _warmup_cost(profile: CompoundProfile, stint_len: int) -> float:
    """Return the total warmup penalty for the first *stint_len* laps.

    Only uses the first ``min(5, stint_len)`` laps and falls back to
    ``0.0`` when the profile has no warmup model.
    """
    if not profile.warmup or stint_len <= 0:
        return 0.0
    warmup = WarmupModel.from_dict(profile.warmup)
    cost = 0.0
    for i in range(min(5, stint_len)):
        cost += warmup.predict_penalty(i)
    return cost


def _pit_cost(
    pit_profile: Optional[PitProfile],
    fuel_to_add: float,
    changing_tires: bool,
    fallback: float,
) -> float:
    """Return the estimated cost of a pit stop.

    Uses the fitted :class:`PitProfile` when provided; otherwise falls
    back to the flat ``fallback`` value.
    """
    if pit_profile is not None:
        cost = pit_profile.compute_cost(fuel_to_add, changing_tires)
        if cost is not None:
            return cost
    return fallback


def _build_stints_for_compound(
    compound: str,
    profile: CompoundProfile,
    total_laps: int,
    fuel_capacity: float,
    pit_time_s: float,
) -> list[PlannedStint]:
    """Build stint list for a single-compound strategy."""
    stints: list[PlannedStint] = []
    lap = 0
    stint_index = 0
    effective_life = _effective_stint_life(profile)

    while lap < total_laps:
        # Determine how many laps this stint can cover
        max_fuel_laps = 0
        fuel_accum = 0.0
        start_fuel = fuel_capacity
        for i in range(total_laps - lap):
            lap_fuel = (
                profile.fuel_curve[i]
                if i < len(profile.fuel_curve)
                else profile.fuel_per_lap
            )
            if fuel_accum + lap_fuel > start_fuel:
                break
            fuel_accum += lap_fuel
            max_fuel_laps += 1

        max_fuel_laps = max(1, max_fuel_laps)
        stint_len = min(max_fuel_laps, effective_life, total_laps - lap)
        stint_len = max(1, stint_len)

        fuel_used = _fuel_for_laps(profile, stint_len)
        grip_end = _grip_at_lap(profile, stint_len - 1)
        time_s = stint_len * profile.avg_lap_time_s

        # Only post-pit stints pay the warmup cost (first lap is cold)
        if stint_index > 0:
            time_s += _warmup_cost(profile, stint_len)

        fuel_to_add = 0.0 if lap == 0 else fuel_capacity

        stints.append(PlannedStint(
            compound=compound,
            start_lap=lap,
            end_lap=lap + stint_len,
            fuel_at_start=start_fuel,
            fuel_to_add=fuel_to_add,
            grip_at_end=grip_end,
            estimated_time_s=time_s,
        ))

        lap += stint_len
        stint_index += 1

    return stints


def _plan_total_time(
    stints: list[PlannedStint],
    pit_time_s: float,
    pit_profile: Optional[PitProfile] = None,
    changing_tires: bool = False,
) -> float:
    """Total race time = driving time + pit stops.

    When *pit_profile* is supplied the per-stop cost is computed from
    the fitted model using each stint's ``fuel_to_add``.
    """
    driving = sum(s.estimated_time_s for s in stints)
    # A pit stop occurs between consecutive stints -- i.e. every stint
    # from index 1 onwards has a preceding pit stop with known fuel add.
    pit_cost_total = 0.0
    for s in stints[1:]:
        pit_cost_total += _pit_cost(
            pit_profile, s.fuel_to_add, changing_tires, pit_time_s,
        )
    return driving + pit_cost_total


def _evaluate_single_compound(
    compound: str,
    profile: CompoundProfile,
    total_laps: int,
    fuel_capacity: float,
    pit_time_s: float,
    pit_profile: Optional[PitProfile] = None,
) -> RacePlan:
    """Evaluate a full race with a single compound."""
    stints = _build_stints_for_compound(
        compound, profile, total_laps, fuel_capacity, pit_time_s,
    )
    # Single-compound runs do not change tires at the stop.
    total_time = _plan_total_time(
        stints, pit_time_s, pit_profile=pit_profile, changing_tires=False,
    )

    # Fuel at finish
    if stints:
        last = stints[-1]
        laps_in_last = last.end_lap - last.start_lap
        fuel_used_last = _fuel_for_laps(profile, laps_in_last)
        fuel_finish = last.fuel_at_start - fuel_used_last
    else:
        fuel_finish = 0.0

    alerts: list[StrategyAlert] = []
    if fuel_finish < 0:
        alerts.append(StrategyAlert(
            severity="critical",
            category="fuel",
            message="Predicted fuel deficit at finish.",
            suggested_action="Reduce pace or add a pit stop.",
        ))
        fuel_finish = 0.0

    return RacePlan(
        stints=stints,
        total_race_time_s=round(total_time, 2),
        fuel_at_finish=round(fuel_finish, 2),
        alerts=alerts,
    )


def _evaluate_two_compound(
    comp_a: str,
    prof_a: CompoundProfile,
    comp_b: str,
    prof_b: CompoundProfile,
    total_laps: int,
    fuel_capacity: float,
    pit_time_s: float,
    pit_profile: Optional[PitProfile] = None,
) -> RacePlan:
    """Evaluate best split between two compounds (one stop)."""
    best: Optional[RacePlan] = None
    life_a = _effective_stint_life(prof_a)
    life_b = _effective_stint_life(prof_b)

    # Try every possible split point for a single pit stop
    for split in range(1, total_laps):
        stint1_laps = split
        stint2_laps = total_laps - split

        # Check fuel feasibility
        fuel1 = _fuel_for_laps(prof_a, stint1_laps)
        fuel2 = _fuel_for_laps(prof_b, stint2_laps)
        if fuel1 > fuel_capacity or fuel2 > fuel_capacity:
            continue

        # Check stint length limits (use fitted model when available)
        if stint1_laps > life_a:
            continue
        if stint2_laps > life_b:
            continue

        grip1 = _grip_at_lap(prof_a, stint1_laps - 1)
        grip2 = _grip_at_lap(prof_b, stint2_laps - 1)

        time1 = stint1_laps * prof_a.avg_lap_time_s
        # Second stint starts after a pit stop -- pay warmup penalty
        time2 = stint2_laps * prof_b.avg_lap_time_s + _warmup_cost(
            prof_b, stint2_laps,
        )

        # A two-compound stop always changes tires.
        pit_cost = _pit_cost(
            pit_profile, fuel_capacity, True, pit_time_s,
        )
        total_time = time1 + time2 + pit_cost

        fuel_finish = fuel_capacity - fuel2

        stints = [
            PlannedStint(
                compound=comp_a,
                start_lap=0,
                end_lap=split,
                fuel_at_start=fuel_capacity,
                fuel_to_add=0.0,
                grip_at_end=grip1,
                estimated_time_s=time1,
            ),
            PlannedStint(
                compound=comp_b,
                start_lap=split,
                end_lap=total_laps,
                fuel_at_start=fuel_capacity,
                fuel_to_add=fuel_capacity,
                grip_at_end=grip2,
                estimated_time_s=time2,
            ),
        ]

        plan = RacePlan(
            stints=stints,
            total_race_time_s=round(total_time, 2),
            fuel_at_finish=round(max(fuel_finish, 0.0), 2),
            alerts=[],
        )

        if best is None or plan.total_race_time_s < best.total_race_time_s:
            best = plan

    return best  # type: ignore[return-value]


# ---------------------------------------------------------------------------
#  Public API — enhanced optimizer
# ---------------------------------------------------------------------------


def optimize_strategy(
    total_laps: int,
    fuel_capacity: float,
    pit_time_s: float,
    profiles: dict[str, CompoundProfile],
    conditions: Optional[list[ConditionWindow]] = None,
    pit_profile: Optional[PitProfile] = None,
    race_mode: str = "laps",
    race_duration_s: float = 0.0,
) -> RacePlan:
    """Optimize race strategy across available compounds.

    Tries every single-compound strategy and every pair of compounds
    (one-stop two-compound), then picks the plan with the lowest total
    race time.

    Parameters
    ----------
    total_laps:
        Total race distance in laps.  Ignored when ``race_mode`` is
        ``"timed"`` and ``race_duration_s`` is positive.
    fuel_capacity:
        Maximum fuel the car can carry (liters).
    pit_time_s:
        Flat fallback pit stop time used when no :class:`PitProfile`
        is available or the profile cannot produce a cost estimate.
    profiles:
        Mapping of compound name to :class:`CompoundProfile`.
    conditions:
        Optional list of :class:`ConditionWindow` for temperature
        correction.  If provided the *first* window's temperature is
        applied uniformly.
    pit_profile:
        Optional fitted :class:`PitProfile` used to compute per-stop
        cost from fuel delta and tire-change flag.  When ``None`` the
        flat ``pit_time_s`` value is used for every stop.
    race_mode:
        ``"laps"`` (default) uses ``total_laps`` as given; ``"timed"``
        converts ``race_duration_s`` into an estimated lap count using
        the first available compound's average lap time.
    race_duration_s:
        Target race duration for timed races (seconds).

    Returns
    -------
    RacePlan
        The fastest feasible strategy.
    """
    if not profiles:
        return RacePlan()

    # Timed-race support: convert duration to estimated lap count.
    if race_mode == "timed" and race_duration_s > 0:
        first_profile = next(iter(profiles.values()))
        avg_lap_time = max(first_profile.avg_lap_time_s, 1e-6)
        total_laps = max(1, int(race_duration_s / avg_lap_time))

    if total_laps <= 0:
        return RacePlan()

    # Apply temperature correction if conditions are provided
    effective_profiles = dict(profiles)
    if conditions:
        temp_c = conditions[0].track_temp_c
        effective_profiles = {
            name: _apply_temp_correction(p, temp_c)
            for name, p in profiles.items()
        }

    candidates: list[RacePlan] = []

    # Single-compound strategies
    for name, prof in effective_profiles.items():
        plan = _evaluate_single_compound(
            name, prof, total_laps, fuel_capacity, pit_time_s,
            pit_profile=pit_profile,
        )
        candidates.append(plan)

    # Two-compound strategies (all ordered pairs)
    compounds = list(effective_profiles.keys())
    for i, ca in enumerate(compounds):
        for j, cb in enumerate(compounds):
            if i == j:
                continue
            plan = _evaluate_two_compound(
                ca, effective_profiles[ca],
                cb, effective_profiles[cb],
                total_laps, fuel_capacity, pit_time_s,
                pit_profile=pit_profile,
            )
            if plan is not None:
                candidates.append(plan)

    if not candidates:
        return RacePlan()

    # Pick the fastest
    best = min(candidates, key=lambda p: p.total_race_time_s)

    # Add weather alerts from conditions
    if conditions:
        for cw in conditions:
            if cw.precipitation > 0.5:
                best.alerts.append(StrategyAlert(
                    severity="warning",
                    category="weather",
                    message=(
                        f"High precipitation expected laps "
                        f"{cw.start_lap}-{cw.end_lap}."
                    ),
                    suggested_action=f"Consider {cw.recommended_compound} tires.",
                ))

    return best


def recalculate_live_plan(
    plan: RacePlan,
    current_lap: int,
    current_fuel: float,
    actual_fuel_deltas: list[float],
    actual_wear: float,
    profiles: dict[str, CompoundProfile],
    fuel_capacity: float,
    pit_time_s: float,
    conditions: Optional[list[ConditionWindow]] = None,
    pit_profile: Optional[PitProfile] = None,
) -> RacePlan:
    """Rebuild a RacePlan from the current race position.

    Uses actual fuel deltas and wear to project forward and generates
    divergence alerts when actuals deviate significantly from the
    original plan.

    Parameters
    ----------
    plan:
        The original (or previously recalculated) plan.
    current_lap:
        Lap just completed (0-indexed, so lap 5 means 5 laps done).
    current_fuel:
        Fuel remaining in the tank right now (liters).
    actual_fuel_deltas:
        Per-lap fuel consumption recorded so far.
    actual_wear:
        Cumulative tire wear observed (0.0 - 1.0).
    profiles:
        Compound profiles available.
    fuel_capacity:
        Maximum fuel capacity (liters).
    pit_time_s:
        Time lost per pit stop.
    conditions:
        Optional track conditions for temperature correction.

    Returns
    -------
    RacePlan
        Updated plan from current position onward.
    """
    alerts: list[StrategyAlert] = []

    # Determine total laps from original plan
    if plan.stints:
        total_laps = plan.stints[-1].end_lap
    else:
        return RacePlan(alerts=[StrategyAlert(
            severity="info",
            category="divergence",
            message="No stints in original plan.",
        )])

    remaining_laps = total_laps - current_lap
    if remaining_laps <= 0:
        return RacePlan(
            stints=[],
            total_race_time_s=0.0,
            fuel_at_finish=current_fuel,
            alerts=[],
        )

    # Calculate actual average fuel consumption
    if actual_fuel_deltas:
        avg_actual_fuel = sum(actual_fuel_deltas) / len(actual_fuel_deltas)
    else:
        # Fallback to first stint's profile
        first_compound = plan.stints[0].compound
        if first_compound in profiles:
            avg_actual_fuel = profiles[first_compound].fuel_per_lap
        else:
            avg_actual_fuel = 3.0  # safe default

    # Check divergence from original planned fuel
    original_compound = plan.stints[0].compound if plan.stints else None
    if original_compound and original_compound in profiles:
        planned_fuel = profiles[original_compound].fuel_per_lap
        fuel_divergence = abs(avg_actual_fuel - planned_fuel) / max(planned_fuel, 0.01)
        if fuel_divergence > 0.10:
            alerts.append(StrategyAlert(
                severity="warning",
                category="divergence",
                message=(
                    f"Fuel consumption diverged {fuel_divergence:.0%} "
                    f"from plan ({avg_actual_fuel:.2f} vs "
                    f"{planned_fuel:.2f} L/lap)."
                ),
                suggested_action="Strategy recalculated with actual rates.",
            ))

    # Check wear divergence
    if current_lap > 0 and original_compound and original_compound in profiles:
        expected_wear = profiles[original_compound].wear_per_lap * current_lap
        if expected_wear > 0:
            wear_divergence = abs(actual_wear - expected_wear) / max(expected_wear, 0.01)
            if wear_divergence > 0.15:
                alerts.append(StrategyAlert(
                    severity="warning",
                    category="tire",
                    message=(
                        f"Tire wear diverged {wear_divergence:.0%} "
                        f"from plan."
                    ),
                    suggested_action="Consider adjusting pit window.",
                ))

    # Build adjusted profiles with actual fuel rate
    adjusted_profiles: dict[str, CompoundProfile] = {}
    for name, prof in profiles.items():
        if name == original_compound:
            adjusted_profiles[name] = CompoundProfile(
                compound=prof.compound,
                fuel_per_lap=avg_actual_fuel,
                fuel_curve=[],  # use adjusted avg
                wear_per_lap=prof.wear_per_lap,
                estimated_life=prof.estimated_life,
                avg_lap_time_s=prof.avg_lap_time_s,
                lap_time_delta_s=prof.lap_time_delta_s,
                avg_track_temp_c=prof.avg_track_temp_c,
                total_laps_logged=prof.total_laps_logged,
                stint_count=prof.stint_count,
                confidence=prof.confidence,
                thermal=prof.thermal,
                warmup=prof.warmup,
                degradation=prof.degradation,
            )
        else:
            adjusted_profiles[name] = prof

    # Re-optimize from current position
    new_plan = optimize_strategy(
        total_laps=remaining_laps,
        fuel_capacity=fuel_capacity,
        pit_time_s=pit_time_s,
        profiles=adjusted_profiles,
        conditions=conditions,
        pit_profile=pit_profile,
    )

    # Shift lap numbers to absolute positions
    for stint in new_plan.stints:
        stint.start_lap += current_lap
        stint.end_lap += current_lap

    # Set fuel_at_start for first stint to actual current fuel
    if new_plan.stints:
        new_plan.stints[0].fuel_at_start = current_fuel

    # Merge alerts
    new_plan.alerts = alerts + new_plan.alerts

    return new_plan
