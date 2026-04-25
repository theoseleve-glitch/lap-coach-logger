"""T155: boundary-value tests for the auto-arm thresholds.

T140's existing :mod:`tests.test_race_strategy_service_auto_arm`
exercises the trigger paths with values well inside or well
outside the thresholds (3 L of fuel, 50 L of fuel, lap 5 vs
lap 14). T155 fills the *boundary* gap: exact equality, just
above, just below — pinning the threshold values so a refactor
that flips ``<=`` to ``<`` (or shifts the threshold by 0.1)
gets caught.

Threshold values (from :mod:`race_strategy_service`):

- ``_FUEL_ARM_THRESHOLD_LAPS = 1.5`` — fuel margin in *laps*
- ``_TIRE_ARM_THRESHOLD_LAPS = 2.0`` — tire stint life in *laps*

Comparison is inclusive (``<=``): exactly at the threshold
arms.

The fuel boundary tests use varying ``fuel_per_lap`` to confirm
the threshold is genuinely in laps, not liters — same 1.5-lap
margin should arm regardless of consumption rate.
"""
from __future__ import annotations

from lap_coach_logger.core.race_strategy_service import RaceStrategyService


def _no_pit_service(
    *,
    total_laps: int = 50,
    fuel_capacity: float = 65.0,
    tire_life_laps: int = 30,
    fuel_per_lap: float = 3.0,
) -> RaceStrategyService:
    """Build a service whose pre-race plan has no scheduled pit
    before the test lap, so ``stint_start_lap = 0`` and the
    tire-stint counter is the raw current lap. Caller picks
    parameters such that no fuel-driven pit appears before the
    range of laps the test cares about."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=total_laps,
        fuel_capacity=fuel_capacity,
        pit_time_s=25.0,
        tire_life_laps=tire_life_laps,
        fuel_per_lap=fuel_per_lap,
    )
    return service


# ---------------------------------------------------------------------------
# Fuel-threshold boundary (1.5 laps, inclusive)
# ---------------------------------------------------------------------------


def test_fuel_exactly_at_threshold_arms() -> None:
    """1.5 laps of fuel = the threshold value. Inclusive
    comparison ⇒ armed. With ``fpl=3.0`` that's 4.5 L."""
    service = _no_pit_service(fuel_per_lap=3.0)

    service.update_armed_state(current_lap=10, current_fuel=4.5)

    assert service.armed is True


def test_fuel_just_above_threshold_does_not_arm() -> None:
    """One percent above the threshold (1.515 laps) — should
    NOT arm. With ``fpl=3.0`` that's 4.545 L. Pinning the
    strict half of the inequality."""
    service = _no_pit_service(fuel_per_lap=3.0)

    service.update_armed_state(current_lap=10, current_fuel=4.545)

    assert service.armed is False


def test_fuel_just_below_threshold_arms() -> None:
    """One percent below the threshold (1.485 laps) — armed
    (and would be even with a strict ``<`` operator). Symmetric
    coverage with the just-above test."""
    service = _no_pit_service(fuel_per_lap=3.0)

    service.update_armed_state(current_lap=10, current_fuel=4.455)

    assert service.armed is True


def test_fuel_threshold_scales_with_fuel_per_lap() -> None:
    """The threshold is in *laps*, not litres. With ``fpl=2.0``,
    1.5 laps = 3.0 L; with ``fpl=4.0``, 1.5 laps = 6.0 L. Both
    arm at their lap-equivalent litres. Pinning catches a
    regression where someone hard-codes a litre threshold."""
    slow_burn = _no_pit_service(fuel_per_lap=2.0)
    fast_burn = _no_pit_service(fuel_per_lap=4.0)

    slow_burn.update_armed_state(current_lap=10, current_fuel=3.0)
    fast_burn.update_armed_state(current_lap=10, current_fuel=6.0)

    assert slow_burn.armed is True
    assert fast_burn.armed is True


# ---------------------------------------------------------------------------
# Tire-threshold boundary (2.0 laps, inclusive)
# ---------------------------------------------------------------------------


def test_tire_exactly_at_threshold_arms() -> None:
    """30-lap tire model on lap 28 = 2 laps of stint left.
    Inclusive comparison ⇒ armed. Plenty of fuel so the fuel
    branch can't be the trigger."""
    # 50-lap race × 65 L tank × 2 L/lap = 130 L total → 1 stop,
    # but tire_life=30 keeps the first scheduled pit at lap 30+,
    # so at lap 28 stint_start_lap is still 0.
    service = _no_pit_service(
        total_laps=50, fuel_capacity=65.0,
        fuel_per_lap=2.0, tire_life_laps=30,
    )
    # Sanity: no pit scheduled before lap 28
    assert service.current is not None
    assert all(s.lap > 28 for s in service.current.pit_stops), (
        "test setup needs no pit before lap 28 so the tire-stint "
        "counter is rooted at 0"
    )

    service.update_armed_state(current_lap=28, current_fuel=65.0)

    assert service.armed is True


def test_tire_one_lap_above_threshold_does_not_arm() -> None:
    """Lap 27 = 3 laps of tire stint left, above the 2.0
    threshold. Plenty of fuel; tire alone wouldn't arm."""
    service = _no_pit_service(
        total_laps=50, fuel_capacity=65.0,
        fuel_per_lap=2.0, tire_life_laps=30,
    )

    service.update_armed_state(current_lap=27, current_fuel=65.0)

    assert service.armed is False
