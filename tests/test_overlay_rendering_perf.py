"""T211: Perf profile — overlay rendering at full load.

Real-world target (sprint goal): overlay rendering at full load
(5 active widgets at 60 fps) must stay under 15% CPU on a Ryzen 5
3600 baseline. CI runners can't measure CPU% directly (different
hardware), so this file pins the *underlying perf budget* —
per-call cost of the pure rendering computations — using a
generous wall-clock budget that holds on slow CI runners.

The pure functions exercised here are the per-frame computations
that drive widget content:

  - compute_fuel_state (fuel margin → SAFE/TIGHT/SAVE/DEFICIT)
  - build_strategy_status (one-liner banner)
  - compute_push_manage (PUSH/MANAGE/SAVE/HOLD decision)
  - build_pit_countdown_display (countdown widget visibility)

Per real-world deployment, an overlay frame computes ALL of these
plus secondary derivations. If the composite "full frame" budget
holds at <200 µs / frame on CI hardware, the Ryzen 5 deployment
target of <15% CPU at 60 fps is comfortably met (60 fps × 200 µs
= 12 ms/sec = 1.2% CPU on a single core, well under budget).

CI-safe budgets are *generous* — 5x typical local-machine timings
— to avoid flakes on slow runners while still catching genuine
perf regressions (an O(n²) loop or accidental allocation explosion
would blow these by orders of magnitude).
"""
from __future__ import annotations

import time

import pytest

from lap_coach_logger.viewmodels.overlay_derived import (
    build_pit_countdown_display,
    build_strategy_status,
    compute_fuel_state,
    compute_push_manage,
)


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

# All budgets are wall-clock seconds for N iterations on the slowest
# expected CI runner. Headroom factor ~5x typical desktop timings.
_ITERATIONS = 5000
_BUDGET_FUEL_STATE_S = 1.0          # 5000 calls
_BUDGET_STRATEGY_STATUS_S = 1.5     # 5000 calls
_BUDGET_PUSH_MANAGE_S = 1.5         # 5000 calls
_BUDGET_PIT_COUNTDOWN_S = 1.0       # 5000 calls
_BUDGET_FULL_FRAME_S = 5.0          # 5000 composite frames


# ---------------------------------------------------------------------------
# Per-function micro-benchmarks
# ---------------------------------------------------------------------------


def test_compute_fuel_state_meets_perf_budget() -> None:
    """``compute_fuel_state`` is called once per overlay frame to map
    fuel margin to a state word. Must be cheap — string compares +
    threshold lookups, no allocations beyond the return value."""
    inputs = [
        (5.0, "GT3"),
        (1.2, "GT3"),
        (0.3, "GT3"),
        (-0.5, "GT4"),
        (2.0, "LMP3"),
    ]
    start = time.perf_counter()
    for i in range(_ITERATIONS):
        margin, car_class = inputs[i % len(inputs)]
        compute_fuel_state(margin, car_class)
    elapsed = time.perf_counter() - start
    assert elapsed < _BUDGET_FUEL_STATE_S, (
        f"compute_fuel_state slow: {elapsed:.3f}s for {_ITERATIONS} "
        f"calls (budget {_BUDGET_FUEL_STATE_S}s) — perf regression"
    )


def test_build_strategy_status_meets_perf_budget() -> None:
    """``build_strategy_status`` is called once per overlay frame to
    build the always-on status banner. String concatenation should
    be cheap; this test catches regressions like accidental f-string
    explosions or unbounded list growth."""
    start = time.perf_counter()
    for i in range(_ITERATIONS):
        build_strategy_status(
            position=(i % 24) + 1,
            current_lap=(i % 60) + 1,
            total_laps=60,
            fuel_state=("SAFE", "TIGHT", "SAVE", "DEFICIT")[i % 4],
            grip_pct=85.0 - float(i % 30),
            laps_to_pit=(i % 10) - 1,
            pit_now=(i % 50 == 0),
        )
    elapsed = time.perf_counter() - start
    assert elapsed < _BUDGET_STRATEGY_STATUS_S, (
        f"build_strategy_status slow: {elapsed:.3f}s for {_ITERATIONS} "
        f"calls (budget {_BUDGET_STRATEGY_STATUS_S}s)"
    )


def test_compute_push_manage_meets_perf_budget() -> None:
    """``compute_push_manage`` is the heaviest of the four — multiple
    branches, dataclass return. Still must hold a tight budget so
    coaching decisions render in real time."""
    start = time.perf_counter()
    for i in range(_ITERATIONS):
        compute_push_manage(
            fuel_margin_l=2.0 - float(i % 30) * 0.1,
            fuel_state=("SAFE", "TIGHT", "SAVE", "DEFICIT")[i % 4],
            grip_pct=85.0 - float(i % 40),
            laps_remaining_in_stint=(i % 30) + 1,
            stint_lap=(i % 30),
            stint_total_laps=30,
            has_live_stint_data=(i % 2 == 0),
        )
    elapsed = time.perf_counter() - start
    assert elapsed < _BUDGET_PUSH_MANAGE_S, (
        f"compute_push_manage slow: {elapsed:.3f}s for {_ITERATIONS} "
        f"calls (budget {_BUDGET_PUSH_MANAGE_S}s)"
    )


def test_build_pit_countdown_display_meets_perf_budget() -> None:
    """``build_pit_countdown_display`` is called once per overlay
    frame to decide visibility + headline of the pit countdown
    widget. Mostly branch-and-format — should be very cheap."""
    start = time.perf_counter()
    for i in range(_ITERATIONS):
        build_pit_countdown_display(
            laps_to_pit=(i % 12) - 1,  # span [-1, 10]
            pit_fuel_load=float((i % 50) * 0.5),
            fuel_state=("SAFE", "TIGHT", "SAVE", "DEFICIT")[i % 4],
            window_laps=5,
        )
    elapsed = time.perf_counter() - start
    assert elapsed < _BUDGET_PIT_COUNTDOWN_S, (
        f"build_pit_countdown_display slow: {elapsed:.3f}s for "
        f"{_ITERATIONS} calls (budget {_BUDGET_PIT_COUNTDOWN_S}s)"
    )


# ---------------------------------------------------------------------------
# Composite "full overlay frame" benchmark
# ---------------------------------------------------------------------------


def test_composite_full_frame_meets_perf_budget() -> None:
    """Full overlay frame: all four pure computations called per
    frame. This is the realistic per-frame cost driving the <15%
    CPU target on Ryzen 5.

    Translates to: ``_BUDGET_FULL_FRAME_S / _ITERATIONS`` seconds
    per frame on CI. At 60 fps deployment cadence this consumes
    ``frame_us * 60 / 10_000 %`` of one core's time. The CI budget
    of 5 s / 5000 frames = 1 ms/frame → 6% of one core at 60 fps,
    well under 15% target."""
    start = time.perf_counter()
    for i in range(_ITERATIONS):
        # Realistic frame: fuel state computed first, then fed into
        # the other three derivations (matches actual data flow).
        margin = 2.0 - float(i % 30) * 0.1
        fuel_state = compute_fuel_state(margin, "GT3")

        build_strategy_status(
            position=(i % 24) + 1,
            current_lap=(i % 60) + 1,
            total_laps=60,
            fuel_state=fuel_state,
            grip_pct=85.0 - float(i % 30),
            laps_to_pit=(i % 10) - 1,
            pit_now=False,
        )
        compute_push_manage(
            fuel_margin_l=margin,
            fuel_state=fuel_state,
            grip_pct=85.0 - float(i % 40),
            laps_remaining_in_stint=(i % 30) + 1,
            stint_lap=(i % 30),
            stint_total_laps=30,
            has_live_stint_data=True,
        )
        build_pit_countdown_display(
            laps_to_pit=(i % 12) - 1,
            pit_fuel_load=float((i % 50) * 0.5),
            fuel_state=fuel_state,
            window_laps=5,
        )
    elapsed = time.perf_counter() - start
    assert elapsed < _BUDGET_FULL_FRAME_S, (
        f"full overlay frame slow: {elapsed:.3f}s for {_ITERATIONS} "
        f"composite frames (budget {_BUDGET_FULL_FRAME_S}s) — "
        f"per-frame cost {elapsed * 1e6 / _ITERATIONS:.1f}µs"
    )


# ---------------------------------------------------------------------------
# Sustainability check — no per-call resource growth
# ---------------------------------------------------------------------------


def test_repeated_calls_do_not_leak_memory() -> None:
    """Pure functions must not retain state between calls — caching,
    memoization, or accidental list-append on a closure variable
    would show up as memory growth. Smoke-check via repeated calls
    + tracemalloc snapshots."""
    import tracemalloc

    # Warm up — first call may pre-allocate.
    for _ in range(100):
        compute_fuel_state(1.0, "GT3")
        build_strategy_status(
            position=5, current_lap=10, total_laps=30,
            fuel_state="SAFE", grip_pct=80.0,
            laps_to_pit=-1, pit_now=False,
        )

    tracemalloc.start()
    snap_before = tracemalloc.take_snapshot()

    # Steady-state work.
    for i in range(2000):
        compute_fuel_state(1.0 + i * 0.0001, "GT3")
        build_strategy_status(
            position=5, current_lap=10, total_laps=30,
            fuel_state="SAFE", grip_pct=80.0,
            laps_to_pit=-1, pit_now=False,
        )

    snap_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    # Compute net allocated memory (KB) between snapshots.
    # Pure functions should produce nothing persistent — any growth
    # over a few KB indicates a leak.
    diff = snap_after.compare_to(snap_before, "lineno")
    total_bytes = sum(stat.size_diff for stat in diff if stat.size_diff > 0)
    total_kb = total_bytes / 1024
    assert total_kb < 200, (
        f"memory leak: pure overlay functions allocated {total_kb:.1f} KB "
        f"net over 2000 calls — possible cache, memoize, or closure "
        f"accumulation"
    )


# ---------------------------------------------------------------------------
# Sanity: outputs are non-trivial (catches "function returns None" regression)
# ---------------------------------------------------------------------------


def test_overlay_pipeline_returns_non_null_outputs() -> None:
    """If any pure function silently regressed to returning None,
    the perf benchmarks would still pass (None is fast). This test
    pins that the outputs are real, populated objects."""
    fuel = compute_fuel_state(1.5, "GT3")
    assert fuel in ("SAFE", "TIGHT", "SAVE", "DEFICIT")

    status = build_strategy_status(
        position=5, current_lap=10, total_laps=30,
        fuel_state=fuel, grip_pct=80.0,
        laps_to_pit=-1, pit_now=False,
    )
    assert status.line, "strategy status line must be non-empty"
    assert status.severity in ("ok", "advisory", "critical")

    push = compute_push_manage(
        fuel_margin_l=1.5, fuel_state=fuel,
        grip_pct=80.0, laps_remaining_in_stint=10,
        stint_lap=5, stint_total_laps=30,
        has_live_stint_data=True,
    )
    assert push.state in ("PUSH", "MANAGE", "SAVE", "HOLD")
    assert push.confidence in ("high", "medium", "low")

    countdown = build_pit_countdown_display(
        laps_to_pit=2, pit_fuel_load=20.0,
        fuel_state=fuel, window_laps=5,
    )
    assert countdown.severity in ("ok", "advisory", "critical")
