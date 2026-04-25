"""T140: ``RaceStrategyService.update_armed_state`` — auto-arm
when fuel window or tire life reaches the pit-window threshold.

T139 shipped the ``armed`` state field as a setter-only
contract. T140 adds the *computation* that decides when the
field should flip on its own:

- if remaining fuel covers fewer than the fuel-arm threshold
  in laps → arm
- if remaining tire-stint life is fewer than the tire-arm
  threshold in laps → arm
- otherwise → disarm

The threshold is met by an OR — either trigger arms. The
caller (T141 / VM) invokes ``update_armed_state`` once per
telemetry snapshot. Manual override via ``arm()`` / ``disarm()``
(T143) interleaves with this; T140 itself is unconditional —
it sets the state purely from current telemetry vs. the
cached strategy.

Tire-stint reset: when planned pit stops have been crossed,
the tire stint counter restarts at the most recent stop's lap.
Without this, a 30-lap tire model would arm permanently after
the first scheduled stop.
"""
from __future__ import annotations

from lap_coach_logger.core.race_strategy_service import RaceStrategyService


def _service_with_strategy(**overrides: object) -> RaceStrategyService:
    """Build a service with a baseline strategy installed."""
    service = RaceStrategyService()
    inputs: dict[str, object] = dict(
        total_laps=50,
        fuel_capacity=65.0,
        pit_time_s=25.0,
        tire_life_laps=30,
        fuel_per_lap=3.0,
    )
    inputs.update(overrides)
    service.compute_pre_race(**inputs)  # type: ignore[arg-type]
    return service


# ---------------------------------------------------------------------------
# No-baseline behaviour
# ---------------------------------------------------------------------------


def test_update_armed_state_returns_current_armed_when_no_strategy() -> None:
    """Without a baseline strategy, the service has no
    fuel/tire reference to threshold against. T140's
    computation must not crash; it must leave ``armed``
    untouched and surface the current value to the caller."""
    service = RaceStrategyService()
    assert service.armed is False

    result = service.update_armed_state(current_lap=10, current_fuel=20.0)

    assert result is False
    assert service.armed is False


# ---------------------------------------------------------------------------
# Fuel-window trigger
# ---------------------------------------------------------------------------


def test_low_fuel_arms_the_pit() -> None:
    """3 L of fuel at 3 L/lap = 1 lap of fuel left — well below
    any reasonable arm threshold. Auto-arm fires."""
    service = _service_with_strategy(fuel_per_lap=3.0)

    service.update_armed_state(current_lap=15, current_fuel=3.0)

    assert service.armed is True


def test_critically_low_fuel_arms_the_pit() -> None:
    """Half a lap of fuel — even more clearly armed. Pinning
    both 'one lap' and 'half lap' so the threshold can be tuned
    without flipping these tests, and so the boundary tests
    aren't the only signal."""
    service = _service_with_strategy(fuel_per_lap=3.0)

    service.update_armed_state(current_lap=15, current_fuel=1.5)

    assert service.armed is True


def test_plenty_of_fuel_keeps_pit_disarmed() -> None:
    """50 L of fuel at 3 L/lap = 16+ laps of fuel — far above
    any fuel-window threshold."""
    service = _service_with_strategy(fuel_per_lap=3.0)

    service.update_armed_state(current_lap=5, current_fuel=50.0)

    assert service.armed is False


# ---------------------------------------------------------------------------
# Tire-life trigger
# ---------------------------------------------------------------------------


def test_tire_stint_near_end_arms_the_pit() -> None:
    """15-lap race on a 65 L tank (no fuel-driven pit stops
    planned), 15-lap tire model, currently on lap 14 — 1 lap
    of tire stint left. Auto-arm fires.

    Scenario chosen so no pit stops are pre-scheduled, keeping
    the tire-stint counter rooted at lap 0 and isolating this
    test from pit-stop scheduling tweaks."""
    service = _service_with_strategy(
        total_laps=15, fuel_capacity=65.0, tire_life_laps=15,
    )

    service.update_armed_state(current_lap=14, current_fuel=50.0)

    assert service.armed is True


def test_tire_stint_at_start_keeps_pit_disarmed() -> None:
    """30-lap tire model, currently on lap 5 — 25 laps of tire
    stint life remaining. Plenty of margin."""
    service = _service_with_strategy(tire_life_laps=30, total_laps=50)

    service.update_armed_state(current_lap=5, current_fuel=50.0)

    assert service.armed is False


def test_tire_stint_resets_after_a_planned_pit_stop() -> None:
    """The default scenario plans pit stops at intervals; the
    tire stint counter must reset at each. Without this, a
    30-lap tire would arm permanently from lap 30 onwards.

    The default 50-lap × 3.0 L/lap × 65 L car plans a stop
    around lap 21 (fuel-limited). On lap 25 (4 laps into the
    second stint) the tire has 26 laps of life left → not
    armed. Pinning this catches a regression where the stint
    counter is computed from the race start."""
    service = _service_with_strategy(
        total_laps=50, fuel_capacity=65.0, fuel_per_lap=3.0,
        tire_life_laps=30,
    )
    # Sanity check: the default plan does include a pit stop
    # before lap 25 — otherwise this test isn't exercising the
    # stint-reset branch.
    assert service.current is not None
    pit_stops_before_25 = [s for s in service.current.pit_stops if s.lap <= 25]
    assert pit_stops_before_25, "test setup invariant: need a pit stop before lap 25"

    service.update_armed_state(current_lap=25, current_fuel=50.0)

    assert service.armed is False


# ---------------------------------------------------------------------------
# OR semantics — either trigger fires
# ---------------------------------------------------------------------------


def test_low_fuel_arms_even_when_tire_is_healthy() -> None:
    """Fuel-only trigger. Tire is fresh (lap 5 of 30-lap stint)
    so the tire branch alone wouldn't arm; fuel forces it."""
    service = _service_with_strategy(tire_life_laps=30, fuel_per_lap=3.0)

    service.update_armed_state(current_lap=5, current_fuel=2.0)

    assert service.armed is True


def test_low_tire_life_arms_even_when_fuel_is_full() -> None:
    """Tire-only trigger. Fuel is full (65 L) so the fuel branch
    alone wouldn't arm; tire stint with 1 lap of life left
    forces it. Same no-pit-stop scenario as
    ``test_tire_stint_near_end_arms_the_pit`` — keeps the test
    robust to pit-stop scheduling changes."""
    service = _service_with_strategy(
        total_laps=15, fuel_capacity=65.0, tire_life_laps=15,
    )

    service.update_armed_state(current_lap=14, current_fuel=65.0)

    assert service.armed is True


# ---------------------------------------------------------------------------
# Disarm path: healthy state actively disarms a previously-armed service
# ---------------------------------------------------------------------------


def test_healthy_state_disarms_previously_armed_service() -> None:
    """Auto-arm computation is *unconditional* on the threshold
    — when neither trigger is met it sets armed=False, even if
    the service was previously armed (manually or by a prior
    auto-arm cycle).

    T143 will introduce manual-override semantics; T140's
    contract is the simpler 'state reflects current telemetry'
    rule. Pinning this catches a regression where the threshold
    only ever turns the field on."""
    service = _service_with_strategy()
    service.arm()  # simulate a prior auto-arm or manual arm
    assert service.armed is True

    service.update_armed_state(current_lap=5, current_fuel=50.0)

    assert service.armed is False


# ---------------------------------------------------------------------------
# Return value matches the post-update state
# ---------------------------------------------------------------------------


def test_update_armed_state_returns_post_update_value() -> None:
    """Caller often needs the new state right away (e.g., to
    drive an immediate UI flag). Return the result rather than
    forcing a follow-up read of ``service.armed``."""
    service = _service_with_strategy(fuel_per_lap=3.0)

    armed_now = service.update_armed_state(current_lap=15, current_fuel=2.0)

    assert armed_now is True
    assert armed_now is service.armed
