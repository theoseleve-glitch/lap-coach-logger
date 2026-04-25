"""T148: Strategy guidance label — PUSH vs MANAGE.

Per the spec a single label tells the driver whether to push
the pace or manage the run, derived from current fuel +
current tire stint position. Used by the strategy widget on
the overlay (T148 surfaces the string; T141 added the pit-arm
indicator already).

Decision rules:

- PUSH — fuel margin is comfortable AND tire stint hasn't
  worn past its critical threshold
- MANAGE — fuel margin is tight (< 1 lap of buffer over the
  remaining race), OR tire stint has used > 70% of its life
- empty string ("") — no baseline strategy yet, or the race
  is over (no useful guidance)

The thresholds are deliberately conservative: 1-lap fuel
buffer keeps the tank-empty cliff one lap further out than
the auto-arm trigger (T140's 1.5 laps), and 70% tire wear
matches the typical "tires falling off" point on a fresh
compound.
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


def test_guidance_returns_empty_when_no_strategy() -> None:
    service = RaceStrategyService()

    result = service.compute_guidance(current_lap=10, current_fuel=30.0)

    assert result == ""


def test_guidance_returns_empty_after_race_finishes() -> None:
    service = _service_with_strategy(total_laps=20)

    result = service.compute_guidance(current_lap=20, current_fuel=10.0)

    assert result == ""


def test_guidance_returns_push_when_fuel_and_tires_are_healthy() -> None:
    service = _service_with_strategy(
        total_laps=50, fuel_capacity=65.0, fuel_per_lap=3.0, tire_life_laps=30,
    )

    result = service.compute_guidance(current_lap=20, current_fuel=50.0)

    assert result == "PUSH"


def test_guidance_returns_manage_when_fuel_margin_is_tight() -> None:
    service = _service_with_strategy(
        total_laps=50, fuel_capacity=65.0, fuel_per_lap=3.0, tire_life_laps=30,
    )

    # 30 laps remaining, 91 L → ~0.3 lap of buffer (< 1.0 threshold)
    result = service.compute_guidance(current_lap=20, current_fuel=91.0)

    assert result == "MANAGE"


def test_guidance_returns_manage_when_fuel_window_is_negative() -> None:
    service = _service_with_strategy(
        total_laps=50, fuel_capacity=65.0, fuel_per_lap=3.0, tire_life_laps=30,
    )

    result = service.compute_guidance(current_lap=20, current_fuel=60.0)

    assert result == "MANAGE"


def test_guidance_returns_manage_when_tire_stint_is_past_critical_threshold() -> None:
    service = _service_with_strategy(
        total_laps=15, fuel_capacity=65.0, fuel_per_lap=3.0, tire_life_laps=15,
    )

    result = service.compute_guidance(current_lap=13, current_fuel=20.0)

    assert result == "MANAGE"


def test_guidance_is_pure_for_given_inputs() -> None:
    service = _service_with_strategy()

    first = service.compute_guidance(current_lap=20, current_fuel=50.0)
    second = service.compute_guidance(current_lap=20, current_fuel=50.0)

    assert first == second == "PUSH"


def test_tire_stint_resets_at_a_planned_pit_lap() -> None:
    service = _service_with_strategy(
        total_laps=50, fuel_capacity=65.0, fuel_per_lap=3.0, tire_life_laps=30,
    )
    assert service.current is not None
    pit_stops_before_25 = [s for s in service.current.pit_stops if s.lap <= 25]
    assert pit_stops_before_25, "test setup: need a pit before lap 25"

    result = service.compute_guidance(current_lap=25, current_fuel=50.0)

    assert result == "PUSH"
