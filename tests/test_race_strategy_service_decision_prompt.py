"""T151: Driver decision prompts — pit / save fuel / push / cool tires.

T148's strategy guidance is a *pace* advisory (PUSH or MANAGE).
T151 sharpens that into a *directive* — what specifically should
the driver do? The four prompts the spec calls out:

- ``"PIT"`` — pit-armed by T140's threshold or T143's manual
  override. Pit entry is the action; nothing else matters until
  the box.
- ``"SAVE FUEL"`` — fuel critically low (< 3 laps in tank,
  matches T148's ``_FUEL_GUIDANCE_CRITICAL_LAPS``). Lift and
  coast.
- ``"COOL TIRES"`` — tire stint past 70% wear (T148's
  ``_TIRE_GUIDANCE_WEAR_PCT``). Smooth inputs, protect the
  rubber to the planned pit.
- ``"PUSH"`` — none of the above; drive it.

Priority is strict and reflects how a race engineer talks to a
driver: PIT overrides everything (the next lap is in the box,
fuel/tire decisions don't apply); SAVE FUEL beats COOL TIRES
(running dry is unrecoverable, tire wear can be nursed); PUSH
is the default when telemetry is healthy.

Empty string for the same edge cases as T148: no baseline plan
yet, or the race is over. The widget renders nothing in those
cases rather than a stale "PUSH" while standing still.
"""
from __future__ import annotations

from lap_coach_logger.core.race_strategy_service import RaceStrategyService


def _service_with_strategy(**overrides: object) -> RaceStrategyService:
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
# Empty edge cases
# ---------------------------------------------------------------------------


def test_prompt_returns_empty_when_no_strategy() -> None:
    service = RaceStrategyService()

    result = service.compute_decision_prompt(current_lap=10, current_fuel=30.0)

    assert result == ""


def test_prompt_returns_empty_after_race_finishes() -> None:
    service = _service_with_strategy(total_laps=20)

    result = service.compute_decision_prompt(current_lap=20, current_fuel=10.0)

    assert result == ""


# ---------------------------------------------------------------------------
# Each prompt fires in isolation
# ---------------------------------------------------------------------------


def test_prompt_returns_push_when_everything_is_healthy() -> None:
    """Default state: pit not armed, fuel comfortable, tires
    fresh. Same scenario as T148's PUSH guidance."""
    service = _service_with_strategy()

    result = service.compute_decision_prompt(current_lap=20, current_fuel=50.0)

    assert result == "PUSH"


def test_prompt_returns_pit_when_service_is_armed() -> None:
    """When the service is pit-armed (T140 threshold or T143
    manual override), the directive is unambiguous: pit. No
    other prompt should override this."""
    service = _service_with_strategy()
    service.arm()  # T139 manual arm — same effect as auto-arm threshold

    result = service.compute_decision_prompt(current_lap=20, current_fuel=50.0)

    assert result == "PIT"


def test_prompt_returns_save_fuel_when_fuel_is_critical() -> None:
    """Fuel < 3 laps in tank ⇒ lift-and-coast. Threshold
    matches T148's _FUEL_GUIDANCE_CRITICAL_LAPS so the prompt
    fires *before* T148 would say MANAGE."""
    service = _service_with_strategy()

    # 8 L / 3.0 fpl = 2.67 laps in tank
    result = service.compute_decision_prompt(current_lap=20, current_fuel=8.0)

    assert result == "SAVE FUEL"


def test_prompt_returns_cool_tires_when_stint_is_worn() -> None:
    """Tire stint > 70% used ⇒ smooth inputs, protect rubber.
    Same threshold as T148's tire guidance, expressed as a
    directive instead of a generic MANAGE."""
    service = _service_with_strategy(
        total_laps=15, fuel_capacity=65.0, fuel_per_lap=3.0, tire_life_laps=15,
    )

    # Lap 13 of 15-lap tire = 86.7% wear; fuel comfortable
    result = service.compute_decision_prompt(current_lap=13, current_fuel=20.0)

    assert result == "COOL TIRES"


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------


def test_pit_beats_save_fuel_when_both_apply() -> None:
    """Armed + fuel critical: still PIT. Once you're in the
    pit lane the SAVE-FUEL directive is moot — refuel takes
    care of fuel margin."""
    service = _service_with_strategy()
    service.arm()

    # Critical fuel, but we're armed
    result = service.compute_decision_prompt(current_lap=20, current_fuel=5.0)

    assert result == "PIT"


def test_save_fuel_beats_cool_tires_when_both_apply() -> None:
    """Fuel critical + worn tires: SAVE FUEL. Running dry is
    unrecoverable; tire wear can be nursed to the planned pit."""
    service = _service_with_strategy(
        total_laps=15, fuel_capacity=65.0, fuel_per_lap=3.0, tire_life_laps=15,
    )

    # Lap 13 of 15-lap tire (worn) AND fuel < 3 laps (critical)
    result = service.compute_decision_prompt(current_lap=13, current_fuel=5.0)

    assert result == "SAVE FUEL"


def test_prompt_is_pure_for_given_inputs() -> None:
    """Same inputs ⇒ same prompt. Mirrors the T148 purity
    test — VM idempotency depends on this."""
    service = _service_with_strategy()

    first = service.compute_decision_prompt(current_lap=20, current_fuel=50.0)
    second = service.compute_decision_prompt(current_lap=20, current_fuel=50.0)

    assert first == second == "PUSH"
