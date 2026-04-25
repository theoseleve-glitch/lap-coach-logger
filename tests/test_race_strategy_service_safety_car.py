"""T149: Safety-car detection + strategy recalc.

iRacing's full-course caution is signalled via the ``"caution"``
or ``"caution_waving"`` flag strings (distinct from ``"yellow"`` /
``"yellow_waving"`` which are *local* yellows for a single
corner). When the strategy service observes a safety-car event we

- recalculate the cached strategy from current telemetry (safety-
  car laps burn fuel and tires slower than green pace, so the pit
  window genuinely shifts), and
- record the lap of the event so the post-race bundle (T146
  plan-vs-actual) can show why the plan diverged from the
  baseline.

The flag classifier is a pure helper so the iRacing adapter can
use it without holding a service reference; the recalc trigger
sits on the service where the cached strategy lives.
"""
from __future__ import annotations

from lap_coach_logger.core.race_strategy_service import (
    RaceStrategyService,
    is_safety_car_flag,
)


# ---------------------------------------------------------------------------
# Flag classifier
# ---------------------------------------------------------------------------


def test_caution_flag_is_safety_car() -> None:
    """``"caution"`` is iRacing's full-course caution — safety
    car deployed. Strategy must react."""
    assert is_safety_car_flag("caution") is True


def test_caution_waving_flag_is_safety_car() -> None:
    """``"caution_waving"`` is the same condition as caution,
    just with the flag waved (transition cue)."""
    assert is_safety_car_flag("caution_waving") is True


def test_green_flag_is_not_safety_car() -> None:
    """Green = racing. No divergence trigger."""
    assert is_safety_car_flag("green") is False


def test_local_yellow_is_not_safety_car() -> None:
    """Local yellow (single corner) is NOT a safety car — the
    field doesn't slow course-wide, so the planned strategy is
    still valid. Pinning both ``"yellow"`` and the waved variant
    so the adapter doesn't accidentally promote a local incident
    to a full-course caution."""
    assert is_safety_car_flag("yellow") is False
    assert is_safety_car_flag("yellow_waving") is False


def test_empty_and_none_flags_are_not_safety_car() -> None:
    """Default / pre-session states. No event, no recalc. Pin
    both ``""`` and ``"none"`` because the iRacing adapter
    returns the latter while the VM defaults to the former."""
    assert is_safety_car_flag("") is False
    assert is_safety_car_flag("none") is False


def test_other_flags_are_not_safety_car() -> None:
    """White (last lap), red (session stopped), checkered (race
    over) are all distinct race events — none of them is a
    safety car. Strategy responses for those are out of scope
    for T149."""
    assert is_safety_car_flag("white") is False
    assert is_safety_car_flag("red") is False
    assert is_safety_car_flag("checkered") is False


# ---------------------------------------------------------------------------
# Service: events list + on_safety_car_detected
# ---------------------------------------------------------------------------


def test_safety_car_events_starts_empty() -> None:
    """Fresh service has no SC history. The bundle field at the
    end of the race should be ``[]`` for a clean run."""
    service = RaceStrategyService()

    assert service.safety_car_events == []


def test_on_safety_car_with_no_baseline_returns_none() -> None:
    """No pre-race strategy ⇒ nothing to recalc against. The
    call is a safe no-op and returns ``None`` — protects the
    pit-from-replay path where SC events can land before the
    plan is computed."""
    service = RaceStrategyService()

    result = service.on_safety_car_detected(
        current_lap=10, current_fuel=30.0, fuel_per_lap=3.0,
    )

    assert result is None
    assert service.safety_car_events == []


def test_on_safety_car_recalculates_strategy() -> None:
    """The recalc IS the divergence handler — re-projecting the
    plan from current telemetry adapts the pit window for the
    slower-pace SC laps. Pin that the cache is updated, the
    same way per-lap recalcs do (T138)."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=50, fuel_capacity=65.0, pit_time_s=25.0,
        tire_life_laps=30, fuel_per_lap=3.0,
    )

    new_strategy = service.on_safety_car_detected(
        current_lap=20, current_fuel=50.0, fuel_per_lap=3.0,
    )

    assert new_strategy is not None
    assert new_strategy is service.current


def test_on_safety_car_records_lap_of_event() -> None:
    """T146 plan-vs-actual reads ``safety_car_events`` to
    explain why the plan diverged. Pin that the lap number is
    captured (not the wall-clock or some derived value)."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=50, fuel_capacity=65.0, pit_time_s=25.0,
        tire_life_laps=30, fuel_per_lap=3.0,
    )

    service.on_safety_car_detected(
        current_lap=15, current_fuel=50.0, fuel_per_lap=3.0,
    )

    assert service.safety_car_events == [15]


def test_on_safety_car_records_multiple_events_in_order() -> None:
    """Long races have multiple SCs. Order is preserved so the
    bundle can show them on a timeline."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=50, fuel_capacity=65.0, pit_time_s=25.0,
        tire_life_laps=30, fuel_per_lap=3.0,
    )

    service.on_safety_car_detected(
        current_lap=12, current_fuel=55.0, fuel_per_lap=3.0,
    )
    service.on_safety_car_detected(
        current_lap=33, current_fuel=40.0, fuel_per_lap=3.0,
    )

    assert service.safety_car_events == [12, 33]


def test_on_safety_car_after_race_finish_returns_none() -> None:
    """SC during a cooldown lap (current_lap >= total_laps) has
    no effect on the strategy — race is over. Don't record it
    either, since the events list represents triggers that
    *changed* the plan."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=20, fuel_capacity=65.0, pit_time_s=25.0,
        tire_life_laps=30, fuel_per_lap=3.0,
    )

    result = service.on_safety_car_detected(
        current_lap=20, current_fuel=10.0, fuel_per_lap=3.0,
    )

    assert result is None
    assert service.safety_car_events == []
