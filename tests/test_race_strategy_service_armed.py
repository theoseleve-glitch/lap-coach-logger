"""T139: ``RaceStrategyService.armed`` state field.

The pit-armed concept (Q102): the strategy service tracks
whether the driver is *armed for a pit stop* — i.e., whether
crossing pit-entry on the next lap should land in the box.
T140 will compute this automatically from fuel-window /
tire-life thresholds; T143 lets the user override it manually.

T139 ships the *state field* in isolation:

- a public ``armed`` boolean (default ``False``)
- ``arm()`` / ``disarm()`` setters (used both by manual override
  in T143 and by the auto-arming logic in T140)
- idempotent — calling ``arm()`` when already armed (or
  ``disarm()`` when already disarmed) is a no-op
- independent of plan computation — pre-race or live recalc
  don't touch the field, so a user's manual arm survives a
  recalc without explicit re-arming

Out of scope: any *automatic* arming logic. T140 will compose
the threshold computation against this field.
"""
from __future__ import annotations

from lap_coach_logger.core.race_strategy_service import RaceStrategyService


# ---------------------------------------------------------------------------
# Default state
# ---------------------------------------------------------------------------


def test_service_starts_disarmed() -> None:
    """A fresh service has not been armed — the user (or auto-
    arm logic) has to opt in. Pinning this catches a regression
    where the field defaults to True (which would falsely cue
    a pit stop on every fresh launch)."""
    service = RaceStrategyService()

    assert service.armed is False


# ---------------------------------------------------------------------------
# arm() / disarm() setters
# ---------------------------------------------------------------------------


def test_arm_sets_armed_to_true() -> None:
    """Manual arm — user clicks 'arm pit' or T140's threshold
    fires. After arm() the field reads True."""
    service = RaceStrategyService()

    service.arm()

    assert service.armed is True


def test_disarm_sets_armed_to_false() -> None:
    """Manual disarm — user changes their mind, or the
    threshold relaxes. After disarm() the field reads False
    again."""
    service = RaceStrategyService()
    service.arm()

    service.disarm()

    assert service.armed is False


def test_arm_is_idempotent_when_already_armed() -> None:
    """Calling arm() twice in a row must not raise or toggle —
    T140 will call this on every snapshot when the threshold is
    crossed, and the auto-arm logic must not require a 'have
    we already armed?' check at every call site."""
    service = RaceStrategyService()
    service.arm()

    service.arm()

    assert service.armed is True


def test_disarm_is_idempotent_when_already_disarmed() -> None:
    """Same reasoning as arm() — symmetry. The auto-arm logic
    in T140 will also drive disarm at every snapshot when the
    threshold is no longer crossed."""
    service = RaceStrategyService()

    service.disarm()  # was already disarmed

    assert service.armed is False


# ---------------------------------------------------------------------------
# Independence from plan computation
# ---------------------------------------------------------------------------


def test_arm_state_persists_across_compute_pre_race() -> None:
    """Re-planning the race (different fuel cap, different lap
    count) does not unset the user's manual arm. The strategy
    *plan* and the *armed* state are orthogonal — a re-plan
    shouldn't silently disarm pit entry."""
    service = RaceStrategyService()
    service.arm()

    service.compute_pre_race(
        total_laps=50,
        fuel_capacity=65.0,
        pit_time_s=25.0,
        tire_life_laps=30,
        fuel_per_lap=3.0,
    )

    assert service.armed is True


def test_arm_state_persists_across_recalculate_from_telemetry() -> None:
    """Same independence on the live side — a per-lap recalc
    must not silently disarm. T140 will hook into recalc to
    update the field deliberately, but the *base* recalc path
    must leave the state alone."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=50,
        fuel_capacity=65.0,
        pit_time_s=25.0,
        tire_life_laps=30,
        fuel_per_lap=3.0,
    )
    service.arm()

    service.recalculate_from_telemetry(
        current_lap=10, current_fuel=35.0, fuel_per_lap=3.0,
    )

    assert service.armed is True


def test_arm_does_not_modify_current_strategy() -> None:
    """The opposite direction: arming the service must not touch
    ``current``. The strategy plan reflects the *race*; the
    armed state reflects the *driver intent*. They live in
    parallel."""
    service = RaceStrategyService()
    strategy = service.compute_pre_race(
        total_laps=50,
        fuel_capacity=65.0,
        pit_time_s=25.0,
        tire_life_laps=30,
        fuel_per_lap=3.0,
    )

    service.arm()

    assert service.current is strategy
