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

# T148 push-vs-manage thresholds.
#
# Three orthogonal MANAGE triggers — fuel is multi-faceted:
#
# - **Margin tight**: buffer over the remaining race is < 1 lap
#   AND the tank can't accept enough refuel to recover (room
#   < 2 laps). With a 65 L tank already at 60 L the next pit only
#   adds ~5 L; you can't push through that. With a 65 L tank at
#   50 L (5 laps room) the next pit refills enough to absorb a
#   negative buffer — that's PUSH.
# - **Fuel critical**: laps-of-fuel-in-tank < 3, regardless of
#   tank room. Even with a planned refill in 2 laps, you might
#   coast empty before reaching it.
# - **Tire wear**: stint has consumed > 70% of life. Matches
#   T140's pit-arm intuition.
_FUEL_GUIDANCE_BUFFER_LAPS = 1.0
_FUEL_GUIDANCE_TANK_ROOM_LAPS = 2.0
_FUEL_GUIDANCE_CRITICAL_LAPS = 3.0
_TIRE_GUIDANCE_WEAR_PCT = 0.70

# T149: iRacing flag strings that signal a *full-course* safety
# car. Local yellows (``"yellow"`` / ``"yellow_waving"``) only
# slow a single corner and don't trigger a strategy divergence.
_SAFETY_CAR_FLAGS = frozenset({"caution", "caution_waving"})

# T150: identifiers that signal a full-course yellow phase
# without (necessarily) a safety car deployment. LMU emits
# ``"full_course_yellow"`` from its session-status enum
# (game phase 6, the Code 60-style FCY phase). Adapters that
# distinguish FCY from SC call ``on_full_course_yellow_detected``
# rather than the safety-car path so the bundle can show which
# kind of caution drove each plan divergence.
_FULL_COURSE_YELLOW_FLAGS = frozenset({"full_course_yellow"})


def is_safety_car_flag(flag_state: str) -> bool:
    """T149: classify an iRacing flag string as safety-car.

    Pure helper so the iRacing adapter can call it without
    holding a service instance (e.g. when forwarding context
    updates). Returns ``True`` only for the full-course caution
    flags — local yellows do not divert the plan.
    """
    return flag_state in _SAFETY_CAR_FLAGS


def is_full_course_yellow_flag(flag_state: str) -> bool:
    """T150: classify a session-status string as full-course
    yellow. Distinct from :func:`is_safety_car_flag` so iRacing's
    caution flags drive the SC path while LMU's
    ``"full_course_yellow"`` drives the FCY path — adapters
    forward whichever identifier their telemetry produces, no
    double-counting because the strings don't overlap.
    """
    return flag_state in _FULL_COURSE_YELLOW_FLAGS


class RaceStrategyService:
    """Stateful orchestrator for race-strategy planning.

    See module docstring for the design rationale. ``current``
    is ``None`` until the first :meth:`compute_pre_race` call.
    """

    def __init__(self) -> None:
        self._current: RaceStrategy | None = None
        self._armed: bool = False
        # T149: laps on which a safety car was detected. Each
        # entry corresponds to a successful recalc trigger; the
        # bundle (T146 plan-vs-actual) reads this to explain
        # divergence from the baseline plan.
        self._safety_car_events: list[int] = []
        # T150: laps on which a full-course yellow phase was
        # detected. Tracked separately from safety-car events
        # so the bundle can show "1 SC + 2 FCY" rather than
        # conflating them as a single caution count.
        self._full_course_yellow_events: list[int] = []

    @property
    def current(self) -> RaceStrategy | None:
        """The most recently computed strategy, or ``None``
        before any computation has run. Distinct from a plan
        with no pit stops (which is a real :class:`RaceStrategy`
        instance with ``num_stops == 0``)."""
        return self._current

    @property
    def safety_car_events(self) -> list[int]:
        """T149: laps at which a safety-car triggered recalcs.
        Returns a *copy* so callers can't mutate the internal
        event log."""
        return list(self._safety_car_events)

    @property
    def full_course_yellow_events(self) -> list[int]:
        """T150: laps at which a full-course yellow triggered
        recalcs. Copy-on-read for the same reason as
        :attr:`safety_car_events`."""
        return list(self._full_course_yellow_events)

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

    def on_safety_car_detected(
        self,
        *,
        current_lap: int,
        current_fuel: float,
        fuel_per_lap: float | None,
    ) -> RaceStrategy | None:
        """T149: handle a safety-car trigger.

        Re-projects the strategy from current telemetry — SC
        laps consume less fuel and tires than green pace, so the
        pit window genuinely shifts — and records ``current_lap``
        in :attr:`safety_car_events` for the post-race bundle.

        Returns ``None`` (and skips recording) when the recalc
        itself is a no-op: no baseline strategy, or the race is
        already over. Mirrors :meth:`recalculate_from_telemetry`'s
        precondition logic so SC events that arrive in those
        states don't pollute the event log.
        """
        new_strategy = self.recalculate_from_telemetry(
            current_lap=current_lap,
            current_fuel=current_fuel,
            fuel_per_lap=fuel_per_lap,
        )
        if new_strategy is None:
            return None
        self._safety_car_events.append(current_lap)
        return new_strategy

    def on_full_course_yellow_detected(
        self,
        *,
        current_lap: int,
        current_fuel: float,
        fuel_per_lap: float | None,
    ) -> RaceStrategy | None:
        """T150: handle a full-course-yellow trigger.

        Same shape as :meth:`on_safety_car_detected` — recalcs
        from current telemetry and records ``current_lap`` in
        :attr:`full_course_yellow_events`. Tracked separately
        from SC events because endurance racing distinguishes
        Code 60-style FCY phases from full SC deployments and
        the post-race bundle should reflect that.
        """
        new_strategy = self.recalculate_from_telemetry(
            current_lap=current_lap,
            current_fuel=current_fuel,
            fuel_per_lap=fuel_per_lap,
        )
        if new_strategy is None:
            return None
        self._full_course_yellow_events.append(current_lap)
        return new_strategy

    def compute_guidance(
        self,
        *,
        current_lap: int,
        current_fuel: float,
    ) -> str:
        """T148: ``"PUSH"`` / ``"MANAGE"`` / ``""`` advisory label.

        Same stint-reset logic as :meth:`update_armed_state` so
        the auto-arm trigger and the guidance label can't disagree
        on which stint is active. Decision rule:

        - Empty (``""``) when no baseline strategy exists yet,
          or the race is over (``current_lap >= total_laps``).
          Avoids surfacing stale advice.
        - ``"MANAGE"`` when the tire stint has used more than
          :data:`_TIRE_GUIDANCE_WEAR_PCT` of its life, OR
          fuel margin is tight (buffer < 1 lap over remaining
          race) AND the tank can't accept enough refuel to fix
          the deficit. With room in the tank, a low buffer is
          PUSH because the next planned pit absorbs it.
        - ``"PUSH"`` otherwise.

        Stricter than the T140 auto-arm thresholds: guidance flips
        to MANAGE *before* the pit indicator arms, so the driver
        starts conserving before the cliff.
        """
        baseline = self._current
        if baseline is None:
            return ""

        laps_remaining = baseline.total_laps - current_lap
        if laps_remaining <= 0:
            return ""

        fpl = max(baseline.fuel_per_lap, 1e-6)
        fuel_laps = current_fuel / fpl
        fuel_buffer_laps = fuel_laps - laps_remaining
        tank_room_laps = (baseline.fuel_capacity - current_fuel) / fpl
        margin_tight = (
            fuel_buffer_laps < _FUEL_GUIDANCE_BUFFER_LAPS
            and tank_room_laps < _FUEL_GUIDANCE_TANK_ROOM_LAPS
        )
        fuel_critical = fuel_laps < _FUEL_GUIDANCE_CRITICAL_LAPS
        fuel_tight = margin_tight or fuel_critical

        # Tire stint resets at most-recent crossed planned pit
        # stop — same convention as T140 update_armed_state.
        stint_start_lap = 0
        for stop in baseline.pit_stops:
            if stop.lap <= current_lap and stop.lap > stint_start_lap:
                stint_start_lap = stop.lap
        laps_into_stint = max(0, current_lap - stint_start_lap)
        tire_wear_pct = (
            laps_into_stint / max(baseline.tire_life_laps, 1)
        )

        manage = fuel_tight or tire_wear_pct > _TIRE_GUIDANCE_WEAR_PCT
        return "MANAGE" if manage else "PUSH"

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


__all__ = [
    "RaceStrategyService",
    "is_safety_car_flag",
    "is_full_course_yellow_flag",
]
