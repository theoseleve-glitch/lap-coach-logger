"""T136: ``RaceStrategyService`` — orchestrator pulled out of the
overlay view-model.

Before T136 the OverlayViewModel inlined the parameter caching,
fuel-per-lap fallbacks, and laps-remaining guards around the
pure :func:`calculate_strategy` / :func:`recalculate_live`
algorithms. T136 lifts that orchestration into a dedicated
domain service so:

- the VM keeps only presentation concerns (the QML signals and
  the ``_apply_strategy`` projection),
- T137 / T138 can grow formal pre-race + live-recalculation
  APIs against a stateful object instead of free-function
  arguments threaded through the VM,
- non-VM callers (CLI, tests, future replay tooling) can drive
  the same orchestration without instantiating a Qt VM.

The pure algorithm functions in :mod:`core.race_strategy` are
unchanged — the service delegates to them.
"""
from __future__ import annotations

import pytest

from lap_coach_logger.core.race_strategy import RaceStrategy
from lap_coach_logger.core.race_strategy_service import RaceStrategyService


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_service_starts_with_no_current_strategy() -> None:
    """A freshly constructed service has not run any computation
    yet — ``current`` is ``None`` so callers can distinguish
    'no plan yet' from 'plan with zero stops'."""
    service = RaceStrategyService()

    assert service.current is None


# ---------------------------------------------------------------------------
# compute_pre_race
# ---------------------------------------------------------------------------


def test_compute_pre_race_returns_strategy_with_pit_stops() -> None:
    """A 50-lap race on a tank that only covers ~21 laps must
    plan at least one pit stop. Pin the basic delegation path
    through the pure :func:`calculate_strategy`."""
    service = RaceStrategyService()

    strategy = service.compute_pre_race(
        total_laps=50,
        fuel_capacity=65.0,
        pit_time_s=25.0,
        tire_life_laps=30,
        fuel_per_lap=3.0,
    )

    assert isinstance(strategy, RaceStrategy)
    assert strategy.total_laps == 50
    assert strategy.num_stops >= 1


def test_compute_pre_race_caches_strategy_as_current() -> None:
    """The service is stateful so live recalculation can rebuild
    from the most recent pre-race plan without the caller having
    to thread it back in. ``current`` reflects the latest
    computation."""
    service = RaceStrategyService()

    strategy = service.compute_pre_race(
        total_laps=50,
        fuel_capacity=65.0,
        pit_time_s=25.0,
        tire_life_laps=30,
        fuel_per_lap=3.0,
    )

    assert service.current is strategy


def test_compute_pre_race_falls_back_to_safe_fuel_when_telemetry_missing() -> None:
    """Pre-race is often computed *before* the telemetry stream
    has reported a fuel-per-lap rate. When ``fuel_per_lap`` is
    ``None`` the service falls back to a conservative default
    instead of dividing by zero or refusing to plan.

    Cross-check via the strategy's own ``fuel_per_lap`` field —
    that's what the live recalculation later uses as its
    baseline, so a wrong default here would cascade."""
    service = RaceStrategyService()

    strategy = service.compute_pre_race(
        total_laps=50,
        fuel_capacity=65.0,
        pit_time_s=25.0,
        tire_life_laps=30,
        fuel_per_lap=None,
    )

    assert strategy.fuel_per_lap == pytest.approx(3.0)


def test_compute_pre_race_falls_back_to_safe_fuel_when_telemetry_zero() -> None:
    """Same fallback when telemetry reports a non-positive value
    (sim hasn't loaded, replay before first lap, etc.). Negative
    or zero would otherwise produce an empty plan."""
    service = RaceStrategyService()

    strategy = service.compute_pre_race(
        total_laps=50,
        fuel_capacity=65.0,
        pit_time_s=25.0,
        tire_life_laps=30,
        fuel_per_lap=0.0,
    )

    assert strategy.fuel_per_lap == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# recalculate_from_telemetry
# ---------------------------------------------------------------------------


def test_recalculate_returns_none_when_no_pre_race_strategy() -> None:
    """Live recalculation needs a baseline. If no pre-race plan
    has been computed the service returns ``None`` instead of
    silently inventing one — the VM uses this to skip its
    ``_apply_strategy`` push."""
    service = RaceStrategyService()

    result = service.recalculate_from_telemetry(
        current_lap=5,
        current_fuel=40.0,
        fuel_per_lap=3.2,
    )

    assert result is None


def test_recalculate_returns_none_when_race_is_finished() -> None:
    """When ``current_lap`` has reached or exceeded the planned
    ``total_laps`` there are no laps left to recalculate. Service
    returns ``None`` — VM's call site uses this to suppress
    re-render after the chequered flag."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=20,
        fuel_capacity=65.0,
        pit_time_s=25.0,
        tire_life_laps=30,
        fuel_per_lap=3.0,
    )

    result = service.recalculate_from_telemetry(
        current_lap=20,  # race over
        current_fuel=10.0,
        fuel_per_lap=3.0,
    )

    assert result is None


def test_recalculate_updates_current_strategy() -> None:
    """Successful recalculation replaces ``current`` so the next
    call uses the updated baseline. Without this the service
    would keep recalculating off the original pre-race plan and
    miss e.g. fuel-rate divergence."""
    service = RaceStrategyService()
    initial = service.compute_pre_race(
        total_laps=50,
        fuel_capacity=65.0,
        pit_time_s=25.0,
        tire_life_laps=30,
        fuel_per_lap=3.0,
    )

    new_strategy = service.recalculate_from_telemetry(
        current_lap=10,
        current_fuel=35.0,
        fuel_per_lap=3.5,  # higher than planned
    )

    assert new_strategy is not None
    assert new_strategy is not initial
    assert service.current is new_strategy


def test_recalculate_falls_back_to_pre_race_fuel_when_telemetry_missing() -> None:
    """If telemetry's fuel-per-lap reading is absent or invalid
    mid-race, the service should fall back to the *pre-race*
    rate (not the safe default) — the pre-race rate is a better
    estimate than 3.0 once any computation has happened."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=50,
        fuel_capacity=65.0,
        pit_time_s=25.0,
        tire_life_laps=30,
        fuel_per_lap=2.7,
    )

    new_strategy = service.recalculate_from_telemetry(
        current_lap=10,
        current_fuel=35.0,
        fuel_per_lap=None,
    )

    assert new_strategy is not None
    assert new_strategy.fuel_per_lap == pytest.approx(2.7)


def test_recalculate_falls_back_when_telemetry_reports_zero() -> None:
    """Same fallback rule when telemetry reports zero / negative
    (e.g., paused sim or first-lap noise). The service should
    not divide by zero downstream."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=50,
        fuel_capacity=65.0,
        pit_time_s=25.0,
        tire_life_laps=30,
        fuel_per_lap=2.7,
    )

    new_strategy = service.recalculate_from_telemetry(
        current_lap=10,
        current_fuel=35.0,
        fuel_per_lap=0.0,
    )

    assert new_strategy is not None
    assert new_strategy.fuel_per_lap == pytest.approx(2.7)
