"""T137: ``RaceStrategyService.compute_pre_race`` API contract.

T136 lifted pre-race orchestration into the service. T137 hardens
the *contract* between the service and its consumers (overlay
view-model, future CLI tools, future replay tooling).

Each behaviour the API promises has a pinning test here so a
future refactor of the underlying ``calculate_strategy`` (or the
service's input handling) can't silently change the shape of the
returned strategy or the inputs it accepts.

Out of scope: anything the upstream :mod:`core.race_strategy`
already pins (tested in :mod:`tests.test_race_strategy`). T137
focuses on the *service-level* contract — what consumers can
rely on from ``RaceStrategyService.compute_pre_race`` itself.
"""
from __future__ import annotations

import pytest

from lap_coach_logger.core.race_strategy import RaceStrategy
from lap_coach_logger.core.race_strategy_service import RaceStrategyService


_DEFAULT_INPUTS = dict(
    total_laps=50,
    fuel_capacity=65.0,
    pit_time_s=25.0,
    tire_life_laps=30,
    fuel_per_lap=3.0,
)


def _service_with_pre_race(**overrides: object) -> tuple[RaceStrategyService, RaceStrategy]:
    """Helper: build a service and run pre-race once, returning
    both. Centralises the dict-merge so tests stay focused on
    the contract under inspection."""
    service = RaceStrategyService()
    inputs = {**_DEFAULT_INPUTS, **overrides}
    strategy = service.compute_pre_race(**inputs)  # type: ignore[arg-type]
    return service, strategy


# ---------------------------------------------------------------------------
# Output reflects each input parameter
# ---------------------------------------------------------------------------


def test_strategy_total_laps_matches_input() -> None:
    """``total_laps`` is a contract value: consumers pin lap-bar
    widgets and pit-arming windows against it. Must round-trip
    unchanged from input to output."""
    _, strategy = _service_with_pre_race(total_laps=42)

    assert strategy.total_laps == 42


def test_strategy_fuel_capacity_matches_input() -> None:
    """Same reasoning as total_laps — fuel-bar widgets need the
    full-tank reference."""
    _, strategy = _service_with_pre_race(fuel_capacity=110.5)

    assert strategy.fuel_capacity == pytest.approx(110.5)


def test_strategy_tire_life_matches_input() -> None:
    """Tire-life ceiling propagates so the consumer can show
    'planned for X-lap stints' in the strategy widget."""
    _, strategy = _service_with_pre_race(tire_life_laps=22)

    assert strategy.tire_life_laps == 22


def test_resolved_fuel_per_lap_propagates_into_strategy() -> None:
    """The fallback rule (None / 0 → 3.0) is internal; the
    *resolved* value must surface on the strategy so live
    recalculation has a baseline to fall back to (T136's
    ``recalculate_from_telemetry`` reads strategy.fuel_per_lap
    when telemetry is invalid)."""
    _, strategy = _service_with_pre_race(fuel_per_lap=None)

    assert strategy.fuel_per_lap == pytest.approx(3.0)


def test_pit_time_propagates_into_total_race_time() -> None:
    """``pit_time_s`` doesn't appear directly on RaceStrategy,
    but a longer pit time must produce a longer total race time
    (everything else equal). Pinning this catches a regression
    where pit_time_s is silently dropped on its way to
    ``calculate_strategy``."""
    _, fast_pits = _service_with_pre_race(pit_time_s=10.0)
    _, slow_pits = _service_with_pre_race(pit_time_s=60.0)

    assert fast_pits.num_stops == slow_pits.num_stops > 0
    assert slow_pits.total_race_time_s > fast_pits.total_race_time_s


# ---------------------------------------------------------------------------
# Stint-sizing behaviour
# ---------------------------------------------------------------------------


def test_short_tire_life_drives_more_pit_stops_than_fuel_alone() -> None:
    """When ``tire_life_laps`` is much shorter than the fuel
    stint, the tire ceiling dictates stop count — the planner
    must respect it. Pinning this prevents a regression where
    tire life is silently ignored (which would be a real
    strategy bug, not just a test bug)."""
    _, fuel_limited = _service_with_pre_race(tire_life_laps=999)
    _, tire_limited = _service_with_pre_race(tire_life_laps=8)

    assert tire_limited.num_stops > fuel_limited.num_stops


def test_long_fuel_range_with_short_race_yields_no_pit_stops() -> None:
    """A 5-lap race on a 65L tank at 3L/lap covers the whole
    distance with fuel to spare. Plan must reflect that — zero
    pit stops, fuel-at-finish > 0."""
    _, strategy = _service_with_pre_race(total_laps=5)

    assert strategy.num_stops == 0
    assert strategy.fuel_at_finish > 0


# ---------------------------------------------------------------------------
# Pit-stop invariants
# ---------------------------------------------------------------------------


def test_every_pit_stop_lap_is_within_race_bounds() -> None:
    """The QML pit-window widget reads ``pit_stops[].lap`` and
    treats it as a lap number to highlight. A negative or
    >total-laps value would render off-screen — a real bug.
    Pinning this catches off-by-one regressions in
    ``calculate_strategy``."""
    _, strategy = _service_with_pre_race()

    assert strategy.num_stops > 0  # smoke check the test is non-trivial
    for stop in strategy.pit_stops:
        assert 0 < stop.lap < strategy.total_laps, (
            f"pit stop at lap {stop.lap} is outside (0, {strategy.total_laps})"
        )


def test_no_pit_stop_adds_more_fuel_than_capacity() -> None:
    """Cars can't be over-fueled. ``fuel_to_add`` must respect
    ``fuel_capacity`` so the consumer can display the figure
    without a defensive cap of its own."""
    _, strategy = _service_with_pre_race()

    assert strategy.num_stops > 0
    for stop in strategy.pit_stops:
        assert stop.fuel_to_add <= strategy.fuel_capacity, (
            f"pit stop adds {stop.fuel_to_add}L > capacity "
            f"{strategy.fuel_capacity}L"
        )


def test_pit_stops_are_in_ascending_lap_order() -> None:
    """The strategy widget renders stops in list order. They
    must already be sorted by lap so the consumer doesn't have
    to re-sort them every frame."""
    _, strategy = _service_with_pre_race()

    laps = [s.lap for s in strategy.pit_stops]
    assert laps == sorted(laps), f"pit stops out of order: {laps}"


# ---------------------------------------------------------------------------
# Cache replacement on successive calls
# ---------------------------------------------------------------------------


def test_successive_calls_replace_cached_current() -> None:
    """User changes the planner inputs (different fuel cap,
    different tire life). Each call must overwrite ``current``
    so live recalculation builds off the latest plan, not a
    stale one."""
    service = RaceStrategyService()

    first = service.compute_pre_race(**_DEFAULT_INPUTS)  # type: ignore[arg-type]
    second_inputs = {**_DEFAULT_INPUTS, "total_laps": 100}
    second = service.compute_pre_race(**second_inputs)  # type: ignore[arg-type]

    assert service.current is second
    assert service.current is not first
    assert second.total_laps == 100


def test_successive_calls_with_identical_inputs_yield_equivalent_plans() -> None:
    """Idempotency: same inputs produce a plan with the same
    shape. Catches a regression where a hidden RNG / clock leak
    sneaks into ``calculate_strategy``."""
    service = RaceStrategyService()

    first = service.compute_pre_race(**_DEFAULT_INPUTS)  # type: ignore[arg-type]
    second = service.compute_pre_race(**_DEFAULT_INPUTS)  # type: ignore[arg-type]

    assert first.num_stops == second.num_stops
    assert first.total_race_time_s == second.total_race_time_s
    assert first.fuel_at_finish == second.fuel_at_finish
    assert [s.lap for s in first.pit_stops] == [s.lap for s in second.pit_stops]


# ---------------------------------------------------------------------------
# Degenerate inputs are tolerated (don't crash; produce empty/safe plan)
# ---------------------------------------------------------------------------


def test_zero_total_laps_returns_strategy_without_pit_stops() -> None:
    """Edge of the input domain: a 0-lap race is meaningless
    but the consumer (overlay) might call into the planner
    before the sim reports a real lap count. Must not crash;
    must produce a plan with no stops."""
    _, strategy = _service_with_pre_race(total_laps=0)

    assert strategy.num_stops == 0


def test_negative_total_laps_returns_strategy_without_pit_stops() -> None:
    """Same as zero, but with negative input (e.g., qualifying
    session passed through as ``-1``). Defensive — must not
    crash, must yield zero stops."""
    _, strategy = _service_with_pre_race(total_laps=-3)

    assert strategy.num_stops == 0
