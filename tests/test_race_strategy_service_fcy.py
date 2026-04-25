"""T150: Full-course-yellow detection + strategy recalc.

Sister to T149's safety-car handler. FCY (Full-Course Yellow)
is a slowed-pace phase that doesn't necessarily deploy a pace
car — Le Mans Ultimate emits ``"full_course_yellow"`` from its
session-status enum (game phase 6, the FCY phase before SC
deployment) and other adapters are expected to emit the same
identifier when their telemetry indicates a course-wide
slowdown.

Why a separate handler from T149's safety-car path:

- iRacing reports ``"caution"`` / ``"caution_waving"`` (its
  full-course caution flags) — those drive the safety-car path.
- LMU has a distinct FCY phase (Code 60-style) that precedes
  the SC. Strategy implications are similar but tracked
  separately so the post-race bundle (T146) can show *which*
  type of caution drove each plan divergence.

Each adapter calls the matching service method; iRacing fires
``on_safety_car_detected`` on its caution flags, LMU fires
``on_full_course_yellow_detected`` on its FCY status. No double-
counting because the flag identifiers don't overlap.
"""
from __future__ import annotations

from lap_coach_logger.core.race_strategy_service import (
    RaceStrategyService,
    is_full_course_yellow_flag,
)


# ---------------------------------------------------------------------------
# Flag classifier
# ---------------------------------------------------------------------------


def test_full_course_yellow_flag_string_is_fcy() -> None:
    """LMU's ``"full_course_yellow"`` from ``_lmu_session_status``
    (game phase 6) is the canonical FCY identifier."""
    assert is_full_course_yellow_flag("full_course_yellow") is True


def test_local_yellow_is_not_fcy() -> None:
    """Single-corner local yellow does NOT slow the field
    course-wide. Mirror of T149's safety-car classifier — the
    distinction between local and full-course is the whole
    point of T150."""
    assert is_full_course_yellow_flag("yellow") is False
    assert is_full_course_yellow_flag("yellow_waving") is False


def test_caution_flags_are_not_fcy() -> None:
    """iRacing's caution flags belong to T149's safety-car path,
    not T150. Keeping them out of the FCY classifier prevents
    iRacing telemetry from double-counting one event in both
    handlers."""
    assert is_full_course_yellow_flag("caution") is False
    assert is_full_course_yellow_flag("caution_waving") is False


def test_green_flag_is_not_fcy() -> None:
    """Racing pace. No divergence trigger."""
    assert is_full_course_yellow_flag("green") is False


def test_empty_and_none_flags_are_not_fcy() -> None:
    """Default / pre-session states. The VM defaults to ``""``
    while LMU returns ``"none"`` — both must be inert."""
    assert is_full_course_yellow_flag("") is False
    assert is_full_course_yellow_flag("none") is False


def test_other_race_flags_are_not_fcy() -> None:
    """White (last lap), red (session stopped), checkered
    (race over) are unrelated to FCY. Pinning them so a
    sloppy classifier extension can't accidentally promote
    those to a divergence trigger."""
    assert is_full_course_yellow_flag("white") is False
    assert is_full_course_yellow_flag("red") is False
    assert is_full_course_yellow_flag("checkered") is False


# ---------------------------------------------------------------------------
# Service: events list + on_full_course_yellow_detected
# ---------------------------------------------------------------------------


def test_full_course_yellow_events_starts_empty() -> None:
    """Fresh service has no FCY history. Bundle field is
    ``[]`` for a clean run with no cautions."""
    service = RaceStrategyService()

    assert service.full_course_yellow_events == []


def test_on_fcy_with_no_baseline_returns_none() -> None:
    """No pre-race plan ⇒ nothing to recalc against. Safe
    no-op that doesn't pollute the event log — protects the
    replay path where FCY events can land before the plan is
    computed."""
    service = RaceStrategyService()

    result = service.on_full_course_yellow_detected(
        current_lap=10, current_fuel=30.0, fuel_per_lap=3.0,
    )

    assert result is None
    assert service.full_course_yellow_events == []


def test_on_fcy_recalculates_strategy() -> None:
    """The recalc handles the divergence — FCY laps burn fuel
    and tires slower, so re-projecting from current telemetry
    adapts the pit window. Pin that the cache is updated, the
    same way T149's safety-car path does."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=50, fuel_capacity=65.0, pit_time_s=25.0,
        tire_life_laps=30, fuel_per_lap=3.0,
    )

    new_strategy = service.on_full_course_yellow_detected(
        current_lap=20, current_fuel=50.0, fuel_per_lap=3.0,
    )

    assert new_strategy is not None
    assert new_strategy is service.current


def test_on_fcy_records_lap_of_event() -> None:
    """T146 plan-vs-actual reads ``full_course_yellow_events``
    to attribute plan divergence. Pin that the lap number
    is captured directly."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=50, fuel_capacity=65.0, pit_time_s=25.0,
        tire_life_laps=30, fuel_per_lap=3.0,
    )

    service.on_full_course_yellow_detected(
        current_lap=18, current_fuel=50.0, fuel_per_lap=3.0,
    )

    assert service.full_course_yellow_events == [18]


def test_on_fcy_records_multiple_events_in_order() -> None:
    """Long endurance races can have multiple FCY phases
    (especially in LMU's Le Mans format). Order is preserved
    so the bundle timeline is correct."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=50, fuel_capacity=65.0, pit_time_s=25.0,
        tire_life_laps=30, fuel_per_lap=3.0,
    )

    service.on_full_course_yellow_detected(
        current_lap=8, current_fuel=58.0, fuel_per_lap=3.0,
    )
    service.on_full_course_yellow_detected(
        current_lap=29, current_fuel=42.0, fuel_per_lap=3.0,
    )

    assert service.full_course_yellow_events == [8, 29]


def test_on_fcy_after_race_finish_returns_none() -> None:
    """FCY during cooldown lap (current_lap >= total_laps)
    has no strategy effect — race is over. Don't record
    either, since events represent triggers that *changed*
    the plan."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=20, fuel_capacity=65.0, pit_time_s=25.0,
        tire_life_laps=30, fuel_per_lap=3.0,
    )

    result = service.on_full_course_yellow_detected(
        current_lap=20, current_fuel=10.0, fuel_per_lap=3.0,
    )

    assert result is None
    assert service.full_course_yellow_events == []


def test_safety_car_and_fcy_events_are_independent() -> None:
    """Different phases must land in different lists so the
    bundle can show "1 SC + 2 FCY phases" rather than
    "3 cautions". Pin that calling one doesn't pollute the
    other."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=50, fuel_capacity=65.0, pit_time_s=25.0,
        tire_life_laps=30, fuel_per_lap=3.0,
    )

    service.on_safety_car_detected(
        current_lap=12, current_fuel=55.0, fuel_per_lap=3.0,
    )
    service.on_full_course_yellow_detected(
        current_lap=25, current_fuel=45.0, fuel_per_lap=3.0,
    )

    assert service.safety_car_events == [12]
    assert service.full_course_yellow_events == [25]
