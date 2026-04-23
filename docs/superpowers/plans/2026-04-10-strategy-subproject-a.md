# Sub-Project A: Realistic Pit + Tire + Endurance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace flat-rate approximations with data-driven fitted models for pit time, tire performance, and endurance race support. Zero hardcoded constants.

**Architecture:** New `strategy_models.py` contains pure fitting functions (OLS, piecewise-linear, exponential decay). `StintRecord` gains per-lap time and temp data. `_aggregate_profile()` calls fitting functions to produce `ThermalModel`, `WarmupModel`, `DegradationModel`. `PitProfile` stores per-track pit measurements and fits a linear model. `race_strategy.py` uses these models instead of flat rates. StrategyVM exposes model availability to QML.

**Tech Stack:** Python 3.12 dataclasses, numpy-free OLS (normal equations), optional numpy for speed.

**Spec:** `docs/superpowers/specs/2026-04-10-strategy-subproject-a-design.md`

---

## Task 1: Model Dataclasses + Fitting Functions

**Files:**
- Create: `src/lap_coach_logger/core/strategy_models.py`
- Test: `tests/test_strategy_models.py`

This task creates all the model dataclasses and pure fitting functions in isolation — no dependencies on stint_store or race_strategy.

- [ ] **Step 1: Write failing tests for ThermalModel fitting**

```python
# tests/test_strategy_models.py
"""Tests for strategy model fitting functions."""
from __future__ import annotations

from lap_coach_logger.core.strategy_models import (
    LapObservation,
    ThermalModel,
    fit_thermal_model,
)


class TestThermalModelFit:

    def test_fit_with_clear_optimal_window(self):
        """Laps in 80-95°C are fast, cold/hot laps are slow."""
        laps = []
        # Cold laps: 60-75°C, slow (+2s per 10°C below 80)
        for temp in [60, 65, 70, 75]:
            penalty = (80 - temp) * 0.2
            laps.append(LapObservation(avg_tyre_temp_c=float(temp), lap_time_s=90.0 + penalty))
        # Optimal laps: 80-95°C, fast
        for temp in [80, 85, 88, 90, 92, 95]:
            laps.append(LapObservation(avg_tyre_temp_c=float(temp), lap_time_s=90.0))
        # Hot laps: 105-120°C, slow
        for temp in [105, 110, 115, 120]:
            penalty = (temp - 95) * 0.3
            laps.append(LapObservation(avg_tyre_temp_c=float(temp), lap_time_s=90.0 + penalty))

        model = fit_thermal_model(laps)
        assert model is not None
        assert model.available is True
        assert 75 <= model.optimal_temp_low <= 85
        assert 90 <= model.optimal_temp_high <= 100
        assert model.cold_penalty_s_per_deg > 0
        assert model.hot_penalty_s_per_deg > 0
        assert model.sample_count == len(laps)

    def test_returns_none_with_insufficient_data(self):
        laps = [LapObservation(avg_tyre_temp_c=85.0, lap_time_s=90.0) for _ in range(3)]
        model = fit_thermal_model(laps)
        assert model is None
```

- [ ] **Step 2: Run tests — verify they fail (module not found)**

Run: `.venv/Scripts/python -m pytest tests/test_strategy_models.py::TestThermalModelFit -v`

- [ ] **Step 3: Create strategy_models.py with LapObservation + ThermalModel + fit_thermal_model**

```python
# src/lap_coach_logger/core/strategy_models.py
"""Data-driven model fitting for race strategy.

All fitting is numpy-free (normal equations for OLS, grid search for
breakpoints). If numpy is available, it's used for speed.

Each fit function returns None when insufficient data — the caller
disables that factor rather than using a hardcoded fallback.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

_MIN_THERMAL_LAPS = 5
_MIN_WARMUP_STINTS = 3
_MIN_DEG_LAPS = 10
_MIN_PIT_MEASUREMENTS = 1


@dataclass
class LapObservation:
    """One lap's observed data for model fitting."""
    avg_tyre_temp_c: float
    lap_time_s: float
    stint_lap_index: int = 0   # 0-based position within stint
    fuel_level: float = 0.0


@dataclass
class ThermalModel:
    optimal_temp_low: float
    optimal_temp_high: float
    cold_penalty_s_per_deg: float
    hot_penalty_s_per_deg: float
    r_squared: float
    sample_count: int
    available: bool

    def predict_penalty(self, temp_c: float) -> float:
        if temp_c < self.optimal_temp_low:
            return self.cold_penalty_s_per_deg * (self.optimal_temp_low - temp_c)
        if temp_c > self.optimal_temp_high:
            return self.hot_penalty_s_per_deg * (temp_c - self.optimal_temp_high)
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "optimal_temp_low": round(self.optimal_temp_low, 1),
            "optimal_temp_high": round(self.optimal_temp_high, 1),
            "cold_penalty_s_per_deg": round(self.cold_penalty_s_per_deg, 4),
            "hot_penalty_s_per_deg": round(self.hot_penalty_s_per_deg, 4),
            "r_squared": round(self.r_squared, 4),
            "sample_count": self.sample_count,
            "available": self.available,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ThermalModel:
        return cls(
            optimal_temp_low=d["optimal_temp_low"],
            optimal_temp_high=d["optimal_temp_high"],
            cold_penalty_s_per_deg=d["cold_penalty_s_per_deg"],
            hot_penalty_s_per_deg=d["hot_penalty_s_per_deg"],
            r_squared=d.get("r_squared", 0),
            sample_count=d.get("sample_count", 0),
            available=d.get("available", False),
        )


def _ols_slope_intercept(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Simple OLS: y = slope*x + intercept. Returns (slope, intercept, r²)."""
    n = len(xs)
    if n < 2:
        return 0.0, 0.0, 0.0
    sx = sum(xs)
    sy = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sxx = sum(x * x for x in xs)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        return 0.0, sy / n, 0.0
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    # R²
    y_mean = sy / n
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r_sq = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return slope, intercept, r_sq


def fit_thermal_model(laps: list[LapObservation]) -> ThermalModel | None:
    """Fit piecewise-linear grip-vs-temperature from lap observations."""
    if len(laps) < _MIN_THERMAL_LAPS:
        return None

    temps = [lap.avg_tyre_temp_c for lap in laps]
    times = [lap.lap_time_s for lap in laps]
    median_time = sorted(times)[len(times) // 2]
    deltas = [t - median_time for t in times]

    min_temp = min(temps)
    max_temp = max(temps)
    if max_temp - min_temp < 5:
        # Not enough temperature range to fit a meaningful model
        return None

    best_cost = float("inf")
    best_low = min_temp
    best_high = max_temp
    best_cold_slope = 0.0
    best_hot_slope = 0.0

    step = max(1.0, (max_temp - min_temp) / 20)
    low_candidates = _frange(min_temp + step, max_temp - step * 2, step)
    for low in low_candidates:
        for high in _frange(low + step, max_temp - step, step):
            cold_xs = [low - t for t, d in zip(temps, deltas) if t < low]
            cold_ys = [d for t, d in zip(temps, deltas) if t < low]
            hot_xs = [t - high for t, d in zip(temps, deltas) if t > high]
            hot_ys = [d for t, d in zip(temps, deltas) if t > high]

            cost = 0.0
            c_slope = 0.0
            h_slope = 0.0
            if len(cold_xs) >= 2:
                c_slope, _, _ = _ols_slope_intercept(cold_xs, cold_ys)
                cost += sum((d - c_slope * x) ** 2 for x, d in zip(cold_xs, cold_ys))
            elif cold_xs:
                cost += sum(d ** 2 for d in cold_ys)
            if len(hot_xs) >= 2:
                h_slope, _, _ = _ols_slope_intercept(hot_xs, hot_ys)
                cost += sum((d - h_slope * x) ** 2 for x, d in zip(hot_xs, hot_ys))
            elif hot_xs:
                cost += sum(d ** 2 for d in hot_ys)
            # Optimal zone residual
            cost += sum(d ** 2 for t, d in zip(temps, deltas) if low <= t <= high)

            if cost < best_cost:
                best_cost = cost
                best_low = low
                best_high = high
                best_cold_slope = max(0.0, c_slope)
                best_hot_slope = max(0.0, h_slope)

    # R² for overall fit
    predicted = []
    for t, d in zip(temps, deltas):
        if t < best_low:
            predicted.append(best_cold_slope * (best_low - t))
        elif t > best_high:
            predicted.append(best_hot_slope * (t - best_high))
        else:
            predicted.append(0.0)
    ss_res = sum((d - p) ** 2 for d, p in zip(deltas, predicted))
    ss_tot = sum(d ** 2 for d in deltas)
    r_sq = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0

    return ThermalModel(
        optimal_temp_low=round(best_low, 1),
        optimal_temp_high=round(best_high, 1),
        cold_penalty_s_per_deg=round(best_cold_slope, 4),
        hot_penalty_s_per_deg=round(best_hot_slope, 4),
        r_squared=round(max(0, r_sq), 4),
        sample_count=len(laps),
        available=True,
    )


def _frange(start: float, stop: float, step: float) -> list[float]:
    result = []
    v = start
    while v <= stop:
        result.append(round(v, 2))
        v += step
    return result
```

- [ ] **Step 4: Run thermal model tests — verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_strategy_models.py::TestThermalModelFit -v`

- [ ] **Step 5: Write failing tests for WarmupModel + DegradationModel**

Add to `tests/test_strategy_models.py`:

```python
from lap_coach_logger.core.strategy_models import (
    DegradationModel,
    StintLapSeries,
    WarmupModel,
    fit_degradation_model,
    fit_warmup_model,
)


class TestWarmupModelFit:

    def test_fit_exponential_warmup(self):
        """First laps are slower, converging to steady-state."""
        stints = []
        for _ in range(4):
            laps = [
                LapObservation(avg_tyre_temp_c=60, lap_time_s=93.0, stint_lap_index=0),
                LapObservation(avg_tyre_temp_c=72, lap_time_s=91.0, stint_lap_index=1),
                LapObservation(avg_tyre_temp_c=82, lap_time_s=90.3, stint_lap_index=2),
                LapObservation(avg_tyre_temp_c=88, lap_time_s=90.0, stint_lap_index=3),
                LapObservation(avg_tyre_temp_c=90, lap_time_s=90.0, stint_lap_index=4),
                LapObservation(avg_tyre_temp_c=90, lap_time_s=90.0, stint_lap_index=5),
            ]
            stints.append(StintLapSeries(laps=laps))

        model = fit_warmup_model(stints)
        assert model is not None
        assert model.amplitude_s > 1.0  # initial penalty > 1s
        assert model.decay_rate > 0     # decays
        assert len(model.raw_penalties) >= 3

    def test_returns_none_with_insufficient_stints(self):
        stints = [StintLapSeries(laps=[
            LapObservation(avg_tyre_temp_c=85, lap_time_s=90.0, stint_lap_index=0),
        ])]
        model = fit_warmup_model(stints)
        assert model is None


class TestDegradationModelFit:

    def test_fit_linear_degradation(self):
        """Laps get progressively slower — linear deg, no cliff."""
        laps = [
            LapObservation(avg_tyre_temp_c=90, lap_time_s=90.0 + i * 0.1, stint_lap_index=i)
            for i in range(20)
        ]
        model = fit_degradation_model(laps)
        assert model is not None
        assert model.available is True
        assert model.deg_rate_per_lap > 0
        assert model.max_viable_stint > 10
        assert model.sample_count == 20

    def test_fit_with_cliff(self):
        """Linear degradation then sudden cliff after lap 12."""
        laps = []
        for i in range(15):
            if i < 12:
                laps.append(LapObservation(avg_tyre_temp_c=90, lap_time_s=90.0 + i * 0.08, stint_lap_index=i))
            else:
                cliff_penalty = (i - 12) ** 2 * 0.5
                laps.append(LapObservation(avg_tyre_temp_c=90, lap_time_s=90.0 + i * 0.08 + cliff_penalty, stint_lap_index=i))
        model = fit_degradation_model(laps)
        assert model is not None
        assert model.cliff_lap is not None
        assert 10 <= model.cliff_lap <= 14

    def test_returns_none_with_insufficient_data(self):
        laps = [LapObservation(avg_tyre_temp_c=90, lap_time_s=90.0, stint_lap_index=0) for _ in range(5)]
        model = fit_degradation_model(laps)
        assert model is None
```

- [ ] **Step 6: Implement WarmupModel, DegradationModel, StintLapSeries, and fit functions**

Add to `src/lap_coach_logger/core/strategy_models.py`:

```python
@dataclass
class StintLapSeries:
    """Per-lap data from one stint, for warmup model fitting."""
    laps: list[LapObservation]


@dataclass
class WarmupModel:
    amplitude_s: float        # A — initial penalty seconds
    decay_rate: float         # k — exp decay rate
    raw_penalties: list[float]  # fallback per-lap penalties
    fitted: bool              # True if exp fit succeeded
    sample_count: int

    def predict_penalty(self, stint_lap: int) -> float:
        if self.fitted:
            return self.amplitude_s * math.exp(-self.decay_rate * stint_lap)
        if stint_lap < len(self.raw_penalties):
            return self.raw_penalties[stint_lap]
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "amplitude_s": round(self.amplitude_s, 3),
            "decay_rate": round(self.decay_rate, 4),
            "raw_penalties": [round(p, 3) for p in self.raw_penalties],
            "fitted": self.fitted,
            "sample_count": self.sample_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WarmupModel:
        return cls(
            amplitude_s=d["amplitude_s"],
            decay_rate=d["decay_rate"],
            raw_penalties=d.get("raw_penalties", []),
            fitted=d.get("fitted", False),
            sample_count=d.get("sample_count", 0),
        )


@dataclass
class DegradationModel:
    deg_rate_per_lap: float
    cliff_lap: int | None
    cliff_rate: float
    max_viable_stint: int
    r_squared: float
    sample_count: int
    available: bool

    def predict_pace_factor(self, stint_lap: int) -> float:
        """Return predicted normalized pace (1.0 = peak, >1.0 = slower)."""
        base = 1.0 + self.deg_rate_per_lap * stint_lap
        if self.cliff_lap is not None and stint_lap > self.cliff_lap:
            base += self.cliff_rate * (stint_lap - self.cliff_lap) ** 2
        return base

    def to_dict(self) -> dict[str, Any]:
        return {
            "deg_rate_per_lap": round(self.deg_rate_per_lap, 6),
            "cliff_lap": self.cliff_lap,
            "cliff_rate": round(self.cliff_rate, 6),
            "max_viable_stint": self.max_viable_stint,
            "r_squared": round(self.r_squared, 4),
            "sample_count": self.sample_count,
            "available": self.available,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DegradationModel:
        return cls(
            deg_rate_per_lap=d["deg_rate_per_lap"],
            cliff_lap=d.get("cliff_lap"),
            cliff_rate=d.get("cliff_rate", 0),
            max_viable_stint=d.get("max_viable_stint", 99),
            r_squared=d.get("r_squared", 0),
            sample_count=d.get("sample_count", 0),
            available=d.get("available", False),
        )


def fit_warmup_model(stints: list[StintLapSeries]) -> WarmupModel | None:
    """Fit exponential decay warmup curve from multiple stints."""
    if len(stints) < _MIN_WARMUP_STINTS:
        return None

    # For each stint, compute per-lap penalty vs steady state
    all_penalties: dict[int, list[float]] = {}
    for stint in stints:
        if len(stint.laps) < 4:
            continue
        steady = sorted(lap.lap_time_s for lap in stint.laps[3:])
        if not steady:
            continue
        steady_time = steady[len(steady) // 2]  # median of laps 4+
        for lap in stint.laps:
            penalty = lap.lap_time_s - steady_time
            all_penalties.setdefault(lap.stint_lap_index, []).append(penalty)

    if not all_penalties:
        return None

    # Average penalty per stint-lap index
    raw_penalties = []
    max_idx = max(all_penalties.keys())
    for i in range(min(max_idx + 1, 10)):
        vals = all_penalties.get(i, [])
        raw_penalties.append(sum(vals) / len(vals) if vals else 0.0)

    # Fit A * exp(-k * x) via log-linear OLS on positive penalties
    xs = []
    ys = []
    for i, p in enumerate(raw_penalties):
        if p > 0.05:  # only fit positive penalties
            xs.append(float(i))
            ys.append(math.log(p))

    total_samples = sum(len(s.laps) for s in stints)

    if len(xs) < 2:
        return WarmupModel(
            amplitude_s=raw_penalties[0] if raw_penalties else 0.0,
            decay_rate=0.0,
            raw_penalties=raw_penalties,
            fitted=False,
            sample_count=total_samples,
        )

    slope, intercept, _ = _ols_slope_intercept(xs, ys)
    amplitude = math.exp(intercept)
    decay_rate = -slope  # slope is negative for decay

    if decay_rate <= 0 or amplitude <= 0:
        return WarmupModel(
            amplitude_s=raw_penalties[0] if raw_penalties else 0.0,
            decay_rate=0.0,
            raw_penalties=raw_penalties,
            fitted=False,
            sample_count=total_samples,
        )

    return WarmupModel(
        amplitude_s=round(amplitude, 3),
        decay_rate=round(decay_rate, 4),
        raw_penalties=[round(p, 3) for p in raw_penalties],
        fitted=True,
        sample_count=total_samples,
    )


def fit_degradation_model(laps: list[LapObservation]) -> DegradationModel | None:
    """Fit linear + cliff degradation from lap observations."""
    if len(laps) < _MIN_DEG_LAPS:
        return None

    best_time = min(lap.lap_time_s for lap in laps)
    if best_time <= 0:
        return None
    normalized = [lap.lap_time_s / best_time for lap in laps]
    indices = [float(lap.stint_lap_index) for lap in laps]

    # Pure linear fit
    slope, intercept, r_sq_linear = _ols_slope_intercept(indices, normalized)
    if slope < 0:
        slope = 0.0

    # Try to find a cliff: test each lap as breakpoint
    best_cliff_cost = float("inf")
    best_cliff_lap = None
    best_cliff_rate = 0.0
    best_cliff_slope = slope

    for bp in range(max(5, len(laps) // 3), len(laps) - 2):
        pre_x = indices[:bp]
        pre_y = normalized[:bp]
        s1, i1, _ = _ols_slope_intercept(pre_x, pre_y)
        if s1 < 0:
            s1 = 0.0

        # Post-cliff: fit quadratic residual
        post_x = [indices[j] - indices[bp] for j in range(bp, len(laps))]
        post_y = [normalized[j] - (s1 * indices[j] + i1) for j in range(bp, len(laps))]
        if len(post_x) >= 2:
            post_x_sq = [x * x for x in post_x]
            c_rate, _, _ = _ols_slope_intercept(post_x_sq, post_y)
            if c_rate <= 0:
                continue
            cost = sum(
                (normalized[j] - (s1 * indices[j] + i1 + c_rate * (indices[j] - indices[bp]) ** 2)) ** 2
                for j in range(len(laps))
            )
            if cost < best_cliff_cost:
                best_cliff_cost = cost
                best_cliff_lap = bp
                best_cliff_rate = c_rate
                best_cliff_slope = s1

    # Compare linear vs cliff model
    linear_cost = sum((n - (slope * x + intercept)) ** 2 for x, n in zip(indices, normalized))

    use_cliff = best_cliff_lap is not None and best_cliff_cost < linear_cost * 0.85

    final_slope = best_cliff_slope if use_cliff else slope
    final_cliff_lap = best_cliff_lap if use_cliff else None
    final_cliff_rate = best_cliff_rate if use_cliff else 0.0

    # Max viable stint: where pace exceeds 1.05 (5% slower than peak)
    max_viable = len(laps)
    for i in range(len(laps)):
        pace = 1.0 + final_slope * i
        if final_cliff_lap is not None and i > final_cliff_lap:
            pace += final_cliff_rate * (i - final_cliff_lap) ** 2
        if pace > 1.05:
            max_viable = i
            break

    # R² for chosen model
    predicted = []
    for x in indices:
        p = 1.0 + final_slope * x
        if final_cliff_lap is not None and x > final_cliff_lap:
            p += final_cliff_rate * (x - final_cliff_lap) ** 2
        predicted.append(p)
    ss_res = sum((n - p) ** 2 for n, p in zip(normalized, predicted))
    mean_n = sum(normalized) / len(normalized)
    ss_tot = sum((n - mean_n) ** 2 for n in normalized)
    r_sq = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0

    return DegradationModel(
        deg_rate_per_lap=round(final_slope, 6),
        cliff_lap=final_cliff_lap,
        cliff_rate=round(final_cliff_rate, 6),
        max_viable_stint=max_viable,
        r_squared=round(max(0, r_sq), 4),
        sample_count=len(laps),
        available=True,
    )
```

- [ ] **Step 7: Run all model tests**

Run: `.venv/Scripts/python -m pytest tests/test_strategy_models.py -v`
Expected: ALL PASS

- [ ] **Step 8: Write failing tests for PitProfile fitting**

Add to `tests/test_strategy_models.py`:

```python
from lap_coach_logger.core.strategy_models import (
    PitMeasurement,
    PitProfile,
    fit_pit_profile,
)


class TestPitProfileFit:

    def test_fit_from_multiple_measurements(self):
        """Two stops with different fuel amounts → fitted linear model."""
        measurements = [
            PitMeasurement(total_time_s=22.0, fuel_added=10.0, tires_changed=False, fuel_at_entry=50, fuel_at_exit=60, compound_before="soft", compound_after="soft", recorded_at=""),
            PitMeasurement(total_time_s=28.0, fuel_added=50.0, tires_changed=False, fuel_at_entry=20, fuel_at_exit=70, compound_before="soft", compound_after="soft", recorded_at=""),
        ]
        profile = fit_pit_profile("Monza", measurements)
        assert profile.beta_transit is not None
        assert profile.beta_fuel_rate is not None
        cost = profile.compute_cost(fuel_to_add=30.0, changing_tires=False)
        assert cost is not None
        assert 22 < cost < 28  # interpolated between the two measurements

    def test_single_measurement_uses_total_time(self):
        measurements = [
            PitMeasurement(total_time_s=25.0, fuel_added=30.0, tires_changed=True, fuel_at_entry=40, fuel_at_exit=70, compound_before="soft", compound_after="medium", recorded_at=""),
        ]
        profile = fit_pit_profile("Monza", measurements)
        assert profile.beta_transit is not None
        assert profile.beta_fuel_rate is None  # can't fit with 1 point
        cost = profile.compute_cost(fuel_to_add=30.0, changing_tires=True)
        assert cost == 25.0  # falls back to measured total

    def test_no_measurements_returns_unavailable(self):
        profile = fit_pit_profile("Monza", [])
        assert profile.beta_transit is None
        assert profile.compute_cost(30.0, False) is None
```

- [ ] **Step 9: Implement PitMeasurement, PitProfile, fit_pit_profile**

Add to `src/lap_coach_logger/core/strategy_models.py`:

```python
@dataclass
class PitMeasurement:
    total_time_s: float
    fuel_added: float
    tires_changed: bool
    fuel_at_entry: float
    fuel_at_exit: float
    compound_before: str
    compound_after: str
    recorded_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_time_s": self.total_time_s,
            "fuel_added": round(self.fuel_added, 2),
            "tires_changed": self.tires_changed,
            "fuel_at_entry": round(self.fuel_at_entry, 2),
            "fuel_at_exit": round(self.fuel_at_exit, 2),
            "compound_before": self.compound_before,
            "compound_after": self.compound_after,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PitMeasurement:
        return cls(
            total_time_s=d["total_time_s"],
            fuel_added=d.get("fuel_added", 0),
            tires_changed=d.get("tires_changed", False),
            fuel_at_entry=d.get("fuel_at_entry", 0),
            fuel_at_exit=d.get("fuel_at_exit", 0),
            compound_before=d.get("compound_before", ""),
            compound_after=d.get("compound_after", ""),
            recorded_at=d.get("recorded_at", ""),
        )


@dataclass
class PitProfile:
    track: str
    beta_transit: float | None = None
    beta_fuel_rate: float | None = None
    beta_tire_change: float | None = None
    r_squared: float | None = None
    measurements: list[PitMeasurement] = field(default_factory=list)

    def compute_cost(self, fuel_to_add: float, changing_tires: bool) -> float | None:
        if self.beta_transit is None:
            return None
        cost = self.beta_transit
        if self.beta_fuel_rate is not None:
            cost += self.beta_fuel_rate * fuel_to_add
        if self.beta_tire_change is not None and changing_tires:
            cost += self.beta_tire_change
        return round(cost, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "track": self.track,
            "beta_transit": self.beta_transit,
            "beta_fuel_rate": self.beta_fuel_rate,
            "beta_tire_change": self.beta_tire_change,
            "r_squared": self.r_squared,
            "measurements": [m.to_dict() for m in self.measurements],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PitProfile:
        return cls(
            track=d["track"],
            beta_transit=d.get("beta_transit"),
            beta_fuel_rate=d.get("beta_fuel_rate"),
            beta_tire_change=d.get("beta_tire_change"),
            r_squared=d.get("r_squared"),
            measurements=[PitMeasurement.from_dict(m) for m in d.get("measurements", [])],
        )


def fit_pit_profile(track: str, measurements: list[PitMeasurement]) -> PitProfile:
    """Fit linear pit time model: time = β₀ + β₁*fuel + β₂*tire_change."""
    profile = PitProfile(track=track, measurements=list(measurements))

    if not measurements:
        return profile

    if len(measurements) == 1:
        profile.beta_transit = measurements[0].total_time_s
        return profile

    # OLS: y = β₀ + β₁*fuel + β₂*tires
    # Build via normal equations: X'X β = X'y
    n = len(measurements)
    ys = [m.total_time_s for m in measurements]
    x_fuel = [m.fuel_added for m in measurements]
    x_tire = [1.0 if m.tires_changed else 0.0 for m in measurements]

    # Check if tire_change has variance
    has_tire_variance = any(m.tires_changed for m in measurements) and not all(m.tires_changed for m in measurements)

    if has_tire_variance:
        # 3-variable OLS
        # X = [[1, fuel, tire], ...]
        sx1 = sum(x_fuel)
        sx2 = sum(x_tire)
        sx1x1 = sum(f * f for f in x_fuel)
        sx2x2 = sum(t * t for t in x_tire)
        sx1x2 = sum(f * t for f, t in zip(x_fuel, x_tire))
        sy = sum(ys)
        sx1y = sum(f * y for f, y in zip(x_fuel, ys))
        sx2y = sum(t * y for t, y in zip(x_tire, ys))
        # Solve 3x3 system via Cramer's rule... or simplify to 2-var first
        # For simplicity, fit fuel rate first, then tire delta from residuals
        slope, intercept, _ = _ols_slope_intercept(x_fuel, ys)
        profile.beta_transit = round(intercept, 2)
        profile.beta_fuel_rate = round(max(0, slope), 4)
        # Tire delta from residuals
        residuals = [y - (intercept + slope * f) for y, f in zip(ys, x_fuel)]
        tire_vals = [r for r, t in zip(residuals, x_tire) if t > 0]
        no_tire_vals = [r for r, t in zip(residuals, x_tire) if t == 0]
        if tire_vals and no_tire_vals:
            profile.beta_tire_change = round(
                sum(tire_vals) / len(tire_vals) - sum(no_tire_vals) / len(no_tire_vals), 2
            )
    else:
        # 2-variable: just transit + fuel rate
        slope, intercept, r_sq = _ols_slope_intercept(x_fuel, ys)
        profile.beta_transit = round(intercept, 2)
        profile.beta_fuel_rate = round(max(0, slope), 4)
        profile.r_squared = round(r_sq, 4)

    return profile
```

- [ ] **Step 10: Run all tests**

Run: `.venv/Scripts/python -m pytest tests/test_strategy_models.py -v`
Expected: ALL PASS

- [ ] **Step 11: Commit**

```bash
git add src/lap_coach_logger/core/strategy_models.py tests/test_strategy_models.py
git commit -m "feat: add data-driven model fitting (thermal, warmup, degradation, pit)"
```

---

## Task 2: Extend StintRecord + StintStore with Per-Lap Data and Models

**Files:**
- Modify: `src/lap_coach_logger/core/stint_store.py`
- Modify: `tests/test_stint_store.py`

- [ ] **Step 1: Add per-lap fields to StintRecord**

Add `lap_times_s: list[float]` and `lap_avg_temps_c: list[float]` to `StintRecord` so model fitting has raw data to work with. Update `to_dict()` and `from_dict()`. These are backward-compatible additions (default to `[]`).

- [ ] **Step 2: Add model fields to CompoundProfile**

Add `thermal: dict | None`, `warmup: dict | None`, `degradation: dict | None` to `CompoundProfile`. Update `to_dict()`. These are serialized model dicts (from `ThermalModel.to_dict()` etc).

- [ ] **Step 3: Update `_aggregate_profile()` to fit models**

Import fitting functions from `strategy_models`. After computing weighted averages, build `LapObservation` lists from all stints' per-lap data and call `fit_thermal_model()`, `fit_warmup_model()`, `fit_degradation_model()`. Store results on the profile.

- [ ] **Step 4: Add PitProfile storage to StintStore**

Add `log_pit_measurement(track, measurement)`, `get_pit_profile(track) -> PitProfile`, and persist pit data in the JSON file under a `"_pit_profiles"` key.

- [ ] **Step 5: Update tests**

Add tests for: StintRecord with per-lap data, CompoundProfile with fitted models, pit profile storage.

- [ ] **Step 6: Run all stint_store tests**

Run: `.venv/Scripts/python -m pytest tests/test_stint_store.py -v`

- [ ] **Step 7: Commit**

```bash
git add src/lap_coach_logger/core/stint_store.py tests/test_stint_store.py
git commit -m "feat: extend StintStore with per-lap data and fitted models"
```

---

## Task 3: Extend StintRecorder with Pit Measurement + Per-Lap Data

**Files:**
- Modify: `src/lap_coach_logger/core/stint_recorder.py`
- Modify: `tests/test_stint_recorder.py`

- [ ] **Step 1: Record per-lap times and temps**

The recorder already tracks `_lap_times` and `_lap_tyre_temps`. Add these to the `StintRecord` on `stop()`: set `lap_times_s=self._lap_times` and `lap_avg_temps_c=[avg of each lap's temps]`.

- [ ] **Step 2: Record PitMeasurement from pit stop telemetry**

Extend the existing pit tracking (already detects `is_in_pits` transitions) to also record `fuel_at_entry`, `fuel_at_exit`, `compound_before`, `compound_after`. Create a `PitMeasurement` on pit exit and call `store.log_pit_measurement()`.

The compound tracking: the recorder knows `self._compound` (set on `start()`). If the compound changes mid-stint (detected via telemetry if sim provides it, or user calls `start()` again with a new compound), that's a tire change.

- [ ] **Step 3: Add tests for per-lap data and pit measurements**

Test that `stop()` returns a StintRecord with populated `lap_times_s` and `lap_avg_temps_c`. Test that pit measurements are recorded to the store.

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_stint_recorder.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/lap_coach_logger/core/stint_recorder.py tests/test_stint_recorder.py
git commit -m "feat: recorder captures per-lap data and pit measurements"
```

---

## Task 4: Update Race Strategy Engine to Use Fitted Models

**Files:**
- Modify: `src/lap_coach_logger/core/race_strategy.py`
- Modify: `tests/test_race_strategy.py`

- [ ] **Step 1: Replace flat pit_time_s with PitProfile**

Change `optimize_strategy()` and `recalculate_live_plan()` to accept an optional `PitProfile`. If available, use `pit_profile.compute_cost(fuel_to_add, changing_tires)` per stop. If `None`, the optimizer warns "pit time unknown."

- [ ] **Step 2: Use WarmupModel in stint time calculation**

When computing estimated stint time, add warmup penalty for the first N laps after each pit stop: `stint_time += sum(warmup.predict_penalty(i) for i in range(min(5, stint_laps)))`.

- [ ] **Step 3: Use DegradationModel for stint limits**

Replace `estimated_life` with `degradation.max_viable_stint` when available. Use `degradation.predict_pace_factor(lap)` for per-lap time estimates instead of flat `avg_lap_time_s`.

- [ ] **Step 4: Use ThermalModel for condition corrections**

Replace `_apply_temp_correction()` with `thermal.predict_penalty(track_temp)` when available. This replaces the hardcoded ±0.3%/°C and ±0.5%/°C.

- [ ] **Step 5: Add timed race support**

Add `race_mode: str = "laps"` and `race_duration_s: float = 0` parameters. For timed races, compute `estimated_total_laps = race_duration_s / avg_lap_time`. The optimizer works with estimated laps internally.

- [ ] **Step 6: Add tests**

Tests for: variable pit cost affecting optimization, warmup penalty in stint costing, degradation cliff limiting stint length, thermal correction from model, timed race mode.

- [ ] **Step 7: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_race_strategy.py -v`

- [ ] **Step 8: Commit**

```bash
git add src/lap_coach_logger/core/race_strategy.py tests/test_race_strategy.py
git commit -m "feat: strategy engine uses fitted models for pit, tire, and endurance"
```

---

## Task 5: Update StrategyViewModel + QML

**Files:**
- Modify: `src/lap_coach_logger/viewmodels/strategy_vm.py`
- Modify: `src/lap_coach_logger/qml/Pages/StrategyPage.qml`
- Modify: `tests/test_strategy_vm.py`

- [ ] **Step 1: Add race mode + model availability to ViewModel**

Add properties: `raceMode` (str), `raceDurationHours` (float), `driverSwapTime` (float). Add `modelAvailability` property that returns per-compound availability status for QML.

- [ ] **Step 2: Pass PitProfile and models to optimizer**

In `autoOptimize()`, load `PitProfile` from store and pass to `optimize_strategy()`. The profiles already contain fitted models from `_aggregate_profile()`.

- [ ] **Step 3: Update QML for lap/timed toggle and model indicators**

Add lap/timed toggle to StrategyPage.qml. Show per-compound model status (thermal: available/needs data, warmup: available/needs data, etc). Add duration input for timed races. Show driver swap fields in timed mode.

- [ ] **Step 4: Add tests**

Test race mode toggle, model availability reporting, timed race estimated laps.

- [ ] **Step 5: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_strategy_vm.py -v`

- [ ] **Step 6: Commit**

```bash
git add src/lap_coach_logger/viewmodels/strategy_vm.py src/lap_coach_logger/qml/Pages/StrategyPage.qml tests/test_strategy_vm.py
git commit -m "feat: strategy UI with race mode toggle and model availability indicators"
```

---

## Task 6: Final Integration Test

**Files:** All modified files

- [ ] **Step 1: Run full test suite**

Run: `.venv/Scripts/python -m pytest tests/ -q --tb=short --ignore=tests/test_desktop_workspaces.py --ignore=tests/test_ghost_widget.py --ignore=tests/test_overlay_browser_frontend.py --ignore=tests/test_overlay_window_manager.py`
Expected: ALL PASS

- [ ] **Step 2: Run Qt widget tests separately**

Run: `.venv/Scripts/python -m pytest tests/test_desktop_workspaces.py tests/test_ghost_widget.py tests/test_overlay_browser_frontend.py tests/test_overlay_window_manager.py -q`
Expected: ALL PASS

- [ ] **Step 3: Verify app launches and strategy page works**

Run: `.venv/Scripts/python -m lap_coach_logger`
Verify Strategy page loads, shows model availability per compound.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: Sub-Project A complete — data-driven pit, tire, and endurance models"
```
