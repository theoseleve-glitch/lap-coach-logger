"""T154: integration test — simulate a lap-by-lap race feed
through :class:`RaceStrategyService` and pin that the pit
window updates correctly.

The unit tests in :mod:`tests.test_race_strategy_service_*`
exercise pre-race + recalc in isolation. T154 covers the
*integration* — many laps of telemetry stream-fed into the
service, the way the OverlayViewModel does at runtime — and
verifies the running ``service.current.pit_stops`` reflects
the actual fuel burn:

- Constant-pace stream → pit window holds near the baseline
  plan (tolerance for the 1-lap discretisation in
  :func:`calculate_strategy`).
- High-burn stream → next pit moves *earlier* than baseline.
- Low-burn stream → next pit moves *later* than baseline (or
  drops out entirely, depending on fuel headroom).

Race parameters (50 laps × 3.0 L/lap × 65 L tank × 30-lap
tire) chosen so the baseline plan is a 2-stop with the first
pit ~1/3 into the race — leaves headroom on both sides for
sim-drift to push the window detectably.
"""
from __future__ import annotations

from lap_coach_logger.core.race_strategy_service import RaceStrategyService


def _baseline_service() -> RaceStrategyService:
    """Pre-race plan used by every sim test below."""
    service = RaceStrategyService()
    service.compute_pre_race(
        total_laps=50, fuel_capacity=65.0, pit_time_s=25.0,
        tire_life_laps=30, fuel_per_lap=3.0,
    )
    return service


def _simulate_laps(
    service: RaceStrategyService,
    *,
    laps: int,
    actual_fuel_per_lap: float,
    starting_fuel: float = 65.0,
) -> None:
    """Push ``laps`` laps of telemetry into the service's
    recalc path. Models the OverlayViewModel's per-lap call
    site: ``recalculate_from_telemetry`` after each lap
    transition."""
    fuel = starting_fuel
    for lap in range(1, laps + 1):
        fuel = max(0.0, fuel - actual_fuel_per_lap)
        service.recalculate_from_telemetry(
            current_lap=lap,
            current_fuel=fuel,
            fuel_per_lap=actual_fuel_per_lap,
        )


# ---------------------------------------------------------------------------
# Baseline reference
# ---------------------------------------------------------------------------


def test_pre_race_baseline_plans_two_pits() -> None:
    """Sanity-check the baseline assumption shared by all the
    sim tests: 50 laps × 3.0 L/lap × 65 L = 2 stops needed."""
    service = _baseline_service()

    assert service.current is not None
    assert service.current.num_stops == 2


# ---------------------------------------------------------------------------
# Constant pace: plan should remain stable
# ---------------------------------------------------------------------------


def test_constant_pace_keeps_pit_window_near_baseline() -> None:
    """Driving at the planned 3.0 L/lap rate ⇒ recalcs project
    the same first-pit lap (within the 1-lap discretisation
    of the planner). Pin the integer stability so a refactor
    that shifts the rounding doesn't go undetected."""
    service = _baseline_service()
    baseline_pit_lap = service.current.pit_stops[0].lap

    _simulate_laps(service, laps=10, actual_fuel_per_lap=3.0)

    next_pit = next(
        (s.lap for s in service.current.pit_stops if s.lap > 10),
        None,
    )
    assert next_pit is not None, (
        "constant pace should still need a pit somewhere ahead"
    )
    assert abs(next_pit - baseline_pit_lap) <= 1


# ---------------------------------------------------------------------------
# Higher burn: pit window moves earlier
# ---------------------------------------------------------------------------


def test_high_burn_moves_next_pit_earlier_than_baseline() -> None:
    """Driving harder than planned (3.5 L/lap vs 3.0) ⇒ tank
    drains faster ⇒ pit must come earlier. Pin the strict
    inequality so the recalc is genuinely reactive — a
    no-op recalc would still match the baseline."""
    service = _baseline_service()
    baseline_pit_lap = service.current.pit_stops[0].lap

    _simulate_laps(service, laps=10, actual_fuel_per_lap=3.5)

    next_pit = next(
        (s.lap for s in service.current.pit_stops if s.lap > 10),
        None,
    )
    assert next_pit is not None
    assert next_pit < baseline_pit_lap, (
        f"high-burn recalc should pull pit earlier than baseline "
        f"{baseline_pit_lap}; got {next_pit}"
    )


# ---------------------------------------------------------------------------
# Lower burn: pit window moves later (or relaxes a stop)
# ---------------------------------------------------------------------------


def test_low_burn_moves_next_pit_later_than_baseline() -> None:
    """Driving easier than planned (2.5 L/lap vs 3.0) ⇒ tank
    lasts longer ⇒ pit can come later. Symmetric to the
    high-burn test."""
    service = _baseline_service()
    baseline_pit_lap = service.current.pit_stops[0].lap

    _simulate_laps(service, laps=10, actual_fuel_per_lap=2.5)

    next_pit = next(
        (s.lap for s in service.current.pit_stops if s.lap > 10),
        None,
    )
    assert next_pit is not None
    assert next_pit > baseline_pit_lap, (
        f"low-burn recalc should push pit later than baseline "
        f"{baseline_pit_lap}; got {next_pit}"
    )


# ---------------------------------------------------------------------------
# Static fields must survive the recalc loop
# ---------------------------------------------------------------------------


def test_total_laps_and_tire_life_are_preserved_across_sim() -> None:
    """Recalc rebuilds the strategy from the cached baseline.
    Static parameters (total_laps, tire_life_laps) must NOT
    drift across the sim — only fuel-related fields adapt.
    Without this guarantee the per-lap recalc loop would
    silently mutate the race definition."""
    service = _baseline_service()
    assert service.current is not None
    initial_total_laps = service.current.total_laps
    initial_tire_life = service.current.tire_life_laps

    _simulate_laps(service, laps=15, actual_fuel_per_lap=3.2)

    assert service.current is not None
    assert service.current.total_laps == initial_total_laps
    assert service.current.tire_life_laps == initial_tire_life


# ---------------------------------------------------------------------------
# Pit window stability: never proposes a pit in the past
# ---------------------------------------------------------------------------


def test_pit_window_never_proposes_a_lap_already_passed() -> None:
    """``recalculate_from_telemetry`` is given ``current_lap``
    and must never project a pit at or before it — that would
    be a logic error (planner can't pit retroactively).
    Iterates 20 laps to give the recalc many chances to slip."""
    service = _baseline_service()

    for lap in range(1, 21):
        service.recalculate_from_telemetry(
            current_lap=lap,
            current_fuel=max(0.0, 65.0 - lap * 3.2),
            fuel_per_lap=3.2,
        )
        assert service.current is not None
        for stop in service.current.pit_stops:
            assert stop.lap > lap, (
                f"recalc at lap {lap} produced a pit at lap "
                f"{stop.lap} — must always be strictly ahead"
            )
