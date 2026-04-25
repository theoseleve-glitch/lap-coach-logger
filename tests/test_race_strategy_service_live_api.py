"""T138: ``RaceStrategyService.recalculate_from_telemetry`` API
contract.

T136 lifted live-recalculation orchestration into the service.
T138 hardens the contract — every guarantee consumers (overlay
VM, divergence-alert engine, future replay tools) get from
``recalculate_from_telemetry`` has a pinning test here.

T136's test file already covers the *control flow* (None
returns when no baseline / race finished, fuel-per-lap
fallbacks, current is replaced). T138 layers on the *content*
contract: the returned plan preserves race scope, projects
forward (not backward), and reacts to telemetry divergence in
the expected direction.
"""
from __future__ import annotations

import pytest

from lap_coach_logger.core.race_strategy_service import RaceStrategyService


_PRE_RACE_INPUTS = dict(
    total_laps=50,
    fuel_capacity=65.0,
    pit_time_s=25.0,
    tire_life_laps=30,
    fuel_per_lap=3.0,
)


def _service_after_pre_race(**overrides: object) -> RaceStrategyService:
    """Helper: build a service with a pre-race plan installed,
    optionally overriding any of the default inputs."""
    service = RaceStrategyService()
    inputs = {**_PRE_RACE_INPUTS, **overrides}
    service.compute_pre_race(**inputs)  # type: ignore[arg-type]
    return service


# ---------------------------------------------------------------------------
# Race scope is preserved (recalc doesn't change the race itself)
# ---------------------------------------------------------------------------


def test_recalc_preserves_total_laps_from_baseline() -> None:
    """A live recalc rebuilds the *plan*, not the race. The
    race's total_laps was set at pre-race; recalculation can't
    change it (the chequered flag is fixed)."""
    service = _service_after_pre_race(total_laps=50)

    new_plan = service.recalculate_from_telemetry(
        current_lap=10, current_fuel=35.0, fuel_per_lap=3.0,
    )

    assert new_plan is not None
    assert new_plan.total_laps == 50


def test_recalc_preserves_fuel_capacity_from_baseline() -> None:
    """Tank size is fixed at the car level — telemetry can't
    change it. Pin this so a future refactor doesn't accidentally
    let it leak through from elsewhere."""
    service = _service_after_pre_race(fuel_capacity=110.5)

    new_plan = service.recalculate_from_telemetry(
        current_lap=10, current_fuel=80.0, fuel_per_lap=3.5,
    )

    assert new_plan is not None
    assert new_plan.fuel_capacity == pytest.approx(110.5)


def test_recalc_preserves_tire_life_from_baseline() -> None:
    """Tire model decisions ride along with the recalc — the
    consumer of the live plan still wants 'planned for X-lap
    stints' to refer to the same tire model."""
    service = _service_after_pre_race(tire_life_laps=22)

    new_plan = service.recalculate_from_telemetry(
        current_lap=5, current_fuel=50.0, fuel_per_lap=3.0,
    )

    assert new_plan is not None
    assert new_plan.tire_life_laps == 22


# ---------------------------------------------------------------------------
# Fuel-rate divergence shows up in the new plan
# ---------------------------------------------------------------------------


def test_recalc_adopts_telemetry_fuel_rate_when_valid() -> None:
    """Telemetry's fuel-per-lap reading is the whole point of
    live recalc. When it's valid (positive), the new plan must
    use it as the fuel_per_lap baseline (not the pre-race
    estimate). Verifies the *primary* divergence input flows
    through end-to-end."""
    service = _service_after_pre_race(fuel_per_lap=3.0)

    new_plan = service.recalculate_from_telemetry(
        current_lap=10, current_fuel=35.0, fuel_per_lap=3.5,
    )

    assert new_plan is not None
    assert new_plan.fuel_per_lap == pytest.approx(3.5)


def test_recalc_with_higher_fuel_use_does_not_decrease_pit_stops() -> None:
    """Driver burning more fuel per lap than planned must not
    *reduce* the number of stops. Direction-of-change pin: a
    regression where divergence flows in the wrong direction
    (e.g., a sign error) gets caught by this comparison."""
    baseline_service = _service_after_pre_race(fuel_per_lap=3.0)
    baseline_plan = baseline_service.recalculate_from_telemetry(
        current_lap=10, current_fuel=35.0, fuel_per_lap=3.0,
    )

    higher_use_service = _service_after_pre_race(fuel_per_lap=3.0)
    higher_use_plan = higher_use_service.recalculate_from_telemetry(
        current_lap=10, current_fuel=35.0, fuel_per_lap=4.0,
    )

    assert baseline_plan is not None
    assert higher_use_plan is not None
    assert higher_use_plan.num_stops >= baseline_plan.num_stops


# ---------------------------------------------------------------------------
# Pit stops project forward, never backward
# ---------------------------------------------------------------------------


def test_recalc_pit_stops_are_all_after_current_lap() -> None:
    """A driver currently on lap 10 doesn't need a pit stop
    scheduled for lap 5. Every recalculated stop must lie at or
    after the current lap — pinning prevents off-by-one
    regressions in the lap-cursor passed through to
    ``calculate_strategy``."""
    service = _service_after_pre_race()

    new_plan = service.recalculate_from_telemetry(
        current_lap=10, current_fuel=35.0, fuel_per_lap=3.0,
    )

    assert new_plan is not None
    for stop in new_plan.pit_stops:
        assert stop.lap >= 10, (
            f"recalc placed a stop at lap {stop.lap} "
            f"before current lap 10"
        )


def test_recalc_pit_stops_are_within_remaining_race() -> None:
    """No stop after the chequered flag either. Stops must live
    in (current_lap, total_laps)."""
    service = _service_after_pre_race(total_laps=50)

    new_plan = service.recalculate_from_telemetry(
        current_lap=10, current_fuel=35.0, fuel_per_lap=3.0,
    )

    assert new_plan is not None
    for stop in new_plan.pit_stops:
        assert stop.lap < 50, (
            f"recalc placed a stop at lap {stop.lap} "
            f"after total_laps 50"
        )


def test_recalc_pit_stops_are_in_ascending_lap_order() -> None:
    """Same ordering contract as pre-race — consumer renders in
    list order."""
    service = _service_after_pre_race()

    new_plan = service.recalculate_from_telemetry(
        current_lap=10, current_fuel=35.0, fuel_per_lap=3.5,
    )

    assert new_plan is not None
    laps = [s.lap for s in new_plan.pit_stops]
    assert laps == sorted(laps), f"recalc stops out of order: {laps}"


# ---------------------------------------------------------------------------
# Successive recalcs replace the cached current
# ---------------------------------------------------------------------------


def test_two_successive_recalcs_each_replace_current() -> None:
    """Live recalc happens once per lap (T136 wires it through
    ``recalculateLiveStrategy`` in the VM). Each call must
    overwrite ``current`` so the next call builds off the latest
    plan, not a stale one — direct parallel to the pre-race
    cache-replacement contract."""
    service = _service_after_pre_race()

    first = service.recalculate_from_telemetry(
        current_lap=10, current_fuel=35.0, fuel_per_lap=3.0,
    )
    second = service.recalculate_from_telemetry(
        current_lap=15, current_fuel=20.0, fuel_per_lap=3.2,
    )

    assert first is not None and second is not None
    assert second is not first
    assert service.current is second


def test_race_finished_recalc_leaves_cached_current_intact() -> None:
    """When recalc returns ``None`` (race over), it must NOT
    mutate ``current`` to ``None`` — the caller often still
    wants to display the final plan post-flag, and silently
    clearing it would crash any consumer reading
    ``service.current.pit_stops``."""
    service = _service_after_pre_race(total_laps=20)
    pre_recalc_current = service.current
    assert pre_recalc_current is not None

    result = service.recalculate_from_telemetry(
        current_lap=20,  # race over
        current_fuel=10.0,
        fuel_per_lap=3.0,
    )

    assert result is None
    assert service.current is pre_recalc_current


def test_no_baseline_recalc_leaves_current_at_none() -> None:
    """Symmetric to the above: with no pre-race plan, ``current``
    is None before the recalc; a None return must not invent
    one."""
    service = RaceStrategyService()
    assert service.current is None

    result = service.recalculate_from_telemetry(
        current_lap=10, current_fuel=35.0, fuel_per_lap=3.0,
    )

    assert result is None
    assert service.current is None


# ---------------------------------------------------------------------------
# Output sanity: a live recalc produces a usable plan
# ---------------------------------------------------------------------------


def test_recalc_produces_non_negative_fuel_at_finish() -> None:
    """``fuel_at_finish`` is a display value (the strategy widget
    shows it as 'expected L at flag'). Negative would render as
    a deficit — but the planner already adds margin, so a
    happy-path recalc must produce a non-negative figure."""
    service = _service_after_pre_race()

    new_plan = service.recalculate_from_telemetry(
        current_lap=10, current_fuel=35.0, fuel_per_lap=3.0,
    )

    assert new_plan is not None
    assert new_plan.fuel_at_finish >= 0


def test_recalc_total_race_time_is_positive() -> None:
    """The remaining-race time estimate must be positive when
    there are still laps to run. Catches a regression where
    the lap-time-derivation collapses to 0 or negative."""
    service = _service_after_pre_race()

    new_plan = service.recalculate_from_telemetry(
        current_lap=10, current_fuel=35.0, fuel_per_lap=3.0,
    )

    assert new_plan is not None
    assert new_plan.total_race_time_s > 0
