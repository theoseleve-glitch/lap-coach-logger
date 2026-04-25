"""T136: ``RaceStrategyService`` — domain service that
orchestrates pre-race + live race-strategy calculation.

The pure algorithms in :mod:`core.race_strategy` (calculate_strategy,
recalculate_live) take every input as an explicit argument. Live
overlay use cases instead want a stateful object that:

- caches the pre-race configuration (``total_laps``,
  ``fuel_capacity``, ``pit_time_s``, ``tire_life_laps``) so live
  recalculation doesn't have to thread them back in,
- holds the most recently computed :class:`RaceStrategy` as
  ``current`` so observers can read the latest plan,
- applies sensible fallbacks when telemetry hasn't yet reported
  a fuel-per-lap rate (pre-race) or reports an invalid one
  (live).

Before T136 the OverlayViewModel inlined this orchestration. T136
extracts it so the VM keeps only QML-presentation concerns and
non-VM callers (CLI tools, tests, replay) can drive the same
logic without instantiating Qt objects.

T137 / T138 will grow formal pre-race + live-recalc APIs on top
of this scaffold.
"""

from __future__ import annotations

from lap_coach_logger.core.race_strategy import (
    RaceStrategy,
    calculate_strategy,
    recalculate_live,
)


# Conservative default used when no telemetry-reported fuel rate
# is available pre-race. Picked to match the OverlayViewModel's
# pre-T136 inline fallback so existing call sites see no change
# in behaviour after the refactor.
_DEFAULT_FUEL_PER_LAP = 3.0

# T140 auto-arming thresholds. Arm the pit when the *smaller* of
# (laps-of-fuel, laps-of-tire-stint) is at or below the
# corresponding threshold. Tuned for typical road-course pit-
# entry decision time — about a lap of buffer beats a hard
# 0-lap cliff that fires too late.
_FUEL_ARM_THRESHOLD_LAPS = 1.5
_TIRE_ARM_THRESHOLD_LAPS = 2.0


class RaceStrategyService:
    """Stateful orchestrator for race-strategy planning.

    See module docstring for the design rationale. ``current``
    is ``None`` until the first :meth:`compute_pre_race` call.
    """

    def __init__(self) -> None:
        self._current: RaceStrategy | None = None
        self._armed: bool = False

    @property
    def current(self) -> RaceStrategy | None:
        """The most recently computed strategy, or ``None``
        before any computation has run. Distinct from a plan
        with no pit stops (which is a real :class:`RaceStrategy`
        instance with ``num_stops == 0``)."""
        return self._current

    @property
    def armed(self) -> bool:
        """T139: pit-armed state. ``True`` when crossing pit
        entry on the next lap should land in the box.

        T140 will set this automatically based on fuel-window /
        tire-life thresholds; T143 lets the user override it
        manually. Default ``False`` — caller must opt in."""
        return self._armed

    def arm(self) -> None:
        """Set :attr:`armed` to ``True``. Idempotent — repeated
        calls are a no-op."""
        self._armed = True

    def disarm(self) -> None:
        """Clear :attr:`armed` back to ``False``. Idempotent."""
        self._armed = False

    def update_armed_state(
        self,
        *,
        current_lap: int,
        current_fuel: float,
    ) -> bool:
        """T140: re-evaluate :attr:`armed` from current telemetry.

        Arms when *either* the fuel window or the tire-stint
        window reaches the pit-entry threshold:

        - laps-of-fuel = ``current_fuel / strategy.fuel_per_lap``
        - laps-of-tire = ``strategy.tire_life_laps - laps_into_stint``,
          where ``laps_into_stint`` resets at every planned pit
          stop the lap cursor has crossed.

        Disarms when neither trigger is met — the result reflects
        current telemetry, not a latched 'once armed always armed'
        state. Manual override (T143) will compose around this.

        With no cached strategy the call is a no-op (no reference
        to threshold against): :attr:`armed` is unchanged and the
        current value is returned.
        """
        baseline = self._current
        if baseline is None:
            return self._armed

        fpl = max(baseline.fuel_per_lap, 1e-6)
        laps_of_fuel = current_fuel / fpl

        # Tire stint resets at the most recent planned pit stop
        # whose lap is <= current_lap. Without this reset, a
        # 30-lap tire model would arm permanently from lap 30
        # onwards even though the planner expects fresh tires
        # after the scheduled stop.
        stint_start_lap = 0
        for stop in baseline.pit_stops:
            if stop.lap <= current_lap and stop.lap > stint_start_lap:
                stint_start_lap = stop.lap
        laps_into_stint = max(0, current_lap - stint_start_lap)
        laps_of_tire = baseline.tire_life_laps - laps_into_stint

        should_arm = (
            laps_of_fuel <= _FUEL_ARM_THRESHOLD_LAPS
            or laps_of_tire <= _TIRE_ARM_THRESHOLD_LAPS
        )
        self._armed = should_arm
        return self._armed

    def compute_pre_race(
        self,
        *,
        total_laps: int,
        fuel_capacity: float,
        pit_time_s: float,
        tire_life_laps: int,
        fuel_per_lap: float | None,
    ) -> RaceStrategy:
        """Compute and cache a pre-race strategy.

        ``fuel_per_lap`` falls back to ``_DEFAULT_FUEL_PER_LAP``
        when ``None`` or non-positive — pre-race is often run
        before the telemetry stream has reported any fuel rate.
        """
        fpl = (
            fuel_per_lap
            if fuel_per_lap is not None and fuel_per_lap > 0
            else _DEFAULT_FUEL_PER_LAP
        )
        self._current = calculate_strategy(
            total_laps=total_laps,
            fuel_capacity=fuel_capacity,
            fuel_per_lap=fpl,
            tire_life_laps=tire_life_laps,
            pit_time_s=pit_time_s,
        )
        return self._current

    def recalculate_from_telemetry(
        self,
        *,
        current_lap: int,
        current_fuel: float,
        fuel_per_lap: float | None,
    ) -> RaceStrategy | None:
        """Rebuild the cached strategy from the current race
        position.

        Returns ``None`` (and leaves ``current`` untouched) when:

        - no pre-race strategy has been computed yet (no
          baseline to recalculate against), or
        - ``current_lap`` has reached or passed the cached
          ``total_laps`` (race is over).

        Invalid telemetry ``fuel_per_lap`` (``None`` or
        non-positive) falls back to the cached strategy's own
        ``fuel_per_lap`` — a better estimate than the pre-race
        default once any computation has happened.
        """
        baseline = self._current
        if baseline is None:
            return None

        laps_remaining = baseline.total_laps - current_lap
        if laps_remaining <= 0:
            return None

        fpl = (
            fuel_per_lap
            if fuel_per_lap is not None and fuel_per_lap > 0
            else baseline.fuel_per_lap
        )
        self._current = recalculate_live(
            strategy=baseline,
            current_lap=current_lap,
            current_fuel=current_fuel,
            actual_fuel_per_lap=fpl,
            laps_remaining=laps_remaining,
        )
        return self._current


__all__ = ["RaceStrategyService"]
