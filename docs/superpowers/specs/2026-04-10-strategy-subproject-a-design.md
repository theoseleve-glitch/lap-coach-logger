# Sub-Project A: Realistic Pit + Tire + Endurance Model — Design Spec

## Overview

Replace the flat-rate approximations in the strategy engine with data-driven
models derived from actual telemetry. Zero hardcoded constants — every parameter
is either directly measured, fitted from logged data, or marked as unavailable
until sufficient data exists.

## Core Principle: No Magic Numbers

Every model parameter falls into one of three states:

| State | Source | Behavior |
|-------|--------|----------|
| **Measured** | Directly observed from telemetry | Used as-is |
| **Fitted** | Regression/curve fit on logged data | Used with confidence interval |
| **Unavailable** | Not enough data yet | Factor disabled in optimizer, UI shows "needs data" |

The system never guesses. If it doesn't have data for a factor, it excludes
that factor from calculations rather than using a fabricated default. The UI
shows exactly which factors are active and which need more data.

## A1: Variable Pit Time Model

### Measurements (from telemetry)

Each pit stop produces a `PitMeasurement`:
```python
@dataclass
class PitMeasurement:
    total_time_s: float       # is_in_pits entry → exit
    fuel_at_entry: float      # fuel_level when is_in_pits goes True
    fuel_at_exit: float       # fuel_level when is_in_pits goes False
    fuel_added: float         # exit - entry
    compound_before: str      # compound entering pit
    compound_after: str       # compound exiting pit
    tires_changed: bool       # compound_before != compound_after
    recorded_at: str
```

### Fitted Model

With 2+ pit measurements, fit a linear model via least-squares:

```
total_time = β₀ + β₁ × fuel_added + β₂ × tires_changed
```

Where:
- `β₀` = pit lane transit time (intercept)
- `β₁` = fuel fill rate (s/liter)
- `β₂` = tire change time delta (s)

With 1 measurement: only `β₀` is known (total time), fuel and tire
components are unavailable.

With 0 measurements: entire pit model is unavailable. Optimizer shows
"pit time unknown — do a pit stop to calibrate."

### PitProfile

```python
@dataclass
class PitProfile:
    track: str
    beta_transit: float | None = None     # β₀ — fitted or single measurement
    beta_fuel_rate: float | None = None   # β₁ — fitted from 2+ stops
    beta_tire_change: float | None = None # β₂ — fitted from mixed stops
    measurements: list[PitMeasurement] = field(default_factory=list)
    r_squared: float | None = None        # fit quality

    def compute_cost(self, fuel_to_add: float, changing_tires: bool) -> float | None:
        if self.beta_transit is None:
            return None  # no data
        cost = self.beta_transit
        if self.beta_fuel_rate is not None:
            cost += self.beta_fuel_rate * fuel_to_add
        if self.beta_tire_change is not None and changing_tires:
            cost += self.beta_tire_change
        return cost

    def refit(self) -> None:
        """Re-run least-squares on all measurements."""
        # ... numpy-free OLS using normal equations
```

Stored per-track in `stint_profiles.json` alongside stint data.

### Optimizer Impact

`optimize_strategy()` calls `pit_profile.compute_cost()` for each planned
stop. If `None` returned (no data), the optimizer cannot evaluate that
strategy variant and warns the user.

## A2: Temperature-Driven Tire Performance Model

### Data Collection (per logged stint)

Each stint already records per-lap:
- `avg_tyre_temp` (average of LF/RF/LR/RR)
- `lap_time_s`
- `fuel_level` delta

From this raw data, we derive three fitted models per compound.

### Model 1: Grip-Temperature Relationship

**Training data:** All laps from all logged stints of a compound, paired:
`(avg_tyre_temp, lap_time_s)`.

**Fitting method:** Piecewise linear regression with a breakpoint search.

1. Collect all `(temp, lap_time)` pairs across stints
2. Normalize lap times: `delta = lap_time - median_lap_time`
3. Find optimal breakpoints by minimizing residual:
   - Fit `delta = α_cold × (breakpoint_low - temp)` for temp < breakpoint_low
   - Fit `delta = α_hot × (temp - breakpoint_high)` for temp > breakpoint_high
   - Laps within `[breakpoint_low, breakpoint_high]` have delta ≈ 0 (optimal window)
4. If insufficient data for piecewise fit (< 20 laps), fall back to single
   linear fit. If < 5 laps, model is unavailable.

**Stored per-compound:**
```python
@dataclass
class ThermalModel:
    optimal_temp_low: float       # °C — fitted breakpoint
    optimal_temp_high: float      # °C — fitted breakpoint
    cold_penalty_s_per_deg: float # seconds/°C below optimal
    hot_penalty_s_per_deg: float  # seconds/°C above optimal
    r_squared: float              # fit quality
    sample_count: int             # laps used for fit
    available: bool               # False if < 5 laps
```

### Model 2: Warmup Curve (Cold Tire Out-Lap)

**Training data:** For each logged stint, take laps 1-6:
`(stint_lap_index, avg_tyre_temp, lap_time_delta_vs_steady_state)`.

`steady_state_time` = median lap time of laps 5+ in that stint (where tires
are at operating temperature).

**Fitting method:** Exponential decay fit.

```
warmup_penalty(stint_lap) = A × exp(-k × stint_lap)
```

Where `A` = initial penalty magnitude, `k` = warmup rate.

Fit `A` and `k` via least-squares on the `(stint_lap, penalty)` pairs
pooled across all stints of that compound.

If < 3 stints: model unavailable. Use the raw per-lap deltas from
whatever stints exist as a lookup table instead of a fitted curve.

**Stored per-compound:**
```python
@dataclass
class WarmupModel:
    amplitude_s: float       # A — initial penalty (seconds)
    decay_rate: float        # k — how fast tires warm up
    raw_penalties: list[float]  # fallback: [lap1_delta, lap2_delta, ...]
    fitted: bool             # True if exp fit succeeded, False = raw fallback
    sample_count: int
```

### Model 3: Degradation Curve

**Training data:** For each logged stint, normalize lap times:
`(stint_lap_index, normalized_pace)` where `normalized_pace = lap_time / best_lap_time_in_stint`.

**Fitting method:** Quadratic or piecewise-linear fit.

- Phase 1 (linear deg): `pace = 1.0 + deg_rate × stint_lap`
- Phase 2 (cliff): After a breakpoint lap, `pace = 1.0 + deg_rate × stint_lap + cliff_rate × (stint_lap - cliff_lap)²`

Find the cliff breakpoint by testing each lap as a candidate and
minimizing the total residual. If no cliff detected (monotonic linear),
use linear-only model.

If < 10 total laps logged: model unavailable. Optimizer uses raw data
points as a lookup table.

**Stored per-compound:**
```python
@dataclass
class DegradationModel:
    deg_rate_per_lap: float       # linear degradation (pace fraction/lap)
    cliff_lap: int | None         # lap where degradation accelerates (None = no cliff)
    cliff_rate: float             # quadratic coefficient after cliff
    max_viable_stint: int         # last lap before pace drops > 5% (derived)
    r_squared: float
    sample_count: int
    available: bool
```

### Wrong Compound Penalty

**Not hardcoded.** Instead, derived from the thermal model:

If the compound's `ThermalModel` has an `optimal_temp_low` of 80°C but
track conditions are 40°C (wet), the thermal model itself predicts the
penalty: `cold_penalty_s_per_deg × (80 - 40) = massive penalty`.

Similarly, wet tires on a dry track at 50°C when their optimal window
is 20-40°C: the hot penalty kicks in naturally.

The only addition needed: when the weather model says "wet" and the planned
compound is a dry compound, flag it as a **WRONG COMPOUND** alert with the
predicted penalty from the thermal model. No hardcoded 8s/lap — the actual
number comes from the fitted curve.

### Minimum Data Requirements

| Model | Min Data | Optimizer Behavior When Unavailable |
|-------|----------|--------------------------------------|
| Thermal | 5 laps | Skip temp correction, use raw lap times |
| Warmup | 3 stints | Skip warmup penalty in stint costing |
| Degradation | 10 laps | Use raw stint length from logged data |
| Pit profile | 1 stop | Warn "pit time unknown", use total measured time as flat cost |
| Fuel curve | 3 laps | Use flat average fuel_per_lap |

### CompoundProfile Changes

Replace current flat fields with model references:

```python
@dataclass
class CompoundProfile:
    compound: str
    fuel_per_lap: float              # weighted average (still useful as summary)
    fuel_curve: list[float]          # per-lap consumption series
    total_laps_logged: int
    stint_count: int
    confidence: str                  # "low" / "medium" / "high"
    avg_track_temp_c: float
    avg_lap_time_s: float
    lap_time_delta_s: float
    # ── Fitted models (new) ──
    thermal: ThermalModel | None     # grip vs temperature
    warmup: WarmupModel | None       # cold tire penalty curve
    degradation: DegradationModel | None  # pace vs stint lap
```

The aggregation function `_aggregate_profile()` now also fits the three
models from the pooled per-lap data across all non-excluded stints.

## A3: Endurance / Time-Based Race Support

### Race Length Modes

```python
race_mode: str = "laps"            # "laps" or "timed"
race_duration_s: float = 0         # for timed races (in seconds)
```

For timed races:
```
estimated_total_laps = race_duration_s / avg_lap_time_s
```

Recalculated live as `avg_lap_time_s` updates from actual data. The
optimizer works internally with `estimated_total_laps` but the UI shows
remaining time, not remaining laps.

### Driver Swap

Not modeled. In sim racing, driver changes are instantaneous — there is
no time cost to switching driver. This differs from real endurance racing
where a driver swap adds 15-45 seconds to a pit stop.

### QML Changes

Strategy page parameters section:
- Toggle: "Lap Race" / "Timed Race" (two buttons, mutually exclusive)
- For lap race: "RACE LAPS" editable field (existing, the only manual input)
- For timed race: "RACE DURATION" editable field (hours:minutes format)
- Show "~N estimated laps" as computed read-only below duration
- Driver swap section: visible only in timed mode, shows swap time + interval

### Auto-Detection

From telemetry session info (when available):
- iRacing: `SessionInfo.Sessions[].SessionLaps` (or "unlimited" for timed)
- iRacing: `SessionInfo.Sessions[].SessionTime` for timed race duration
- LMU: `mMaxLaps` from shared memory (0 = timed race)
- ACC: session type in shared memory

If detected as timed race, auto-switch mode and populate duration.

## Model Fitting Implementation

All model fitting lives in a new module:

**`src/lap_coach_logger/core/strategy_models.py`**

Contains pure functions that take raw stint data and return fitted model
dataclasses. No sim-specific logic. No persistence (that's StintStore's job).

```python
def fit_thermal_model(laps: list[LapObservation]) -> ThermalModel | None:
    """Fit piecewise-linear grip-vs-temperature model."""

def fit_warmup_model(stints: list[StintLapSeries]) -> WarmupModel | None:
    """Fit exponential decay warmup curve."""

def fit_degradation_model(laps: list[LapObservation]) -> DegradationModel | None:
    """Fit linear + cliff degradation curve."""

def fit_pit_profile(measurements: list[PitMeasurement]) -> PitProfile:
    """Fit pit time linear model via OLS."""
```

Each function returns `None` when insufficient data. The fitting uses
numpy-free implementations (normal equations for OLS, grid search for
breakpoints) to avoid adding numpy as a runtime dependency (it's already
optional for tests only).

If numpy IS available at runtime (user installed it), use it for faster
fitting. Graceful degradation:

```python
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
```

## Files to Create

| File | Purpose |
|------|---------|
| `src/lap_coach_logger/core/strategy_models.py` | All model fitting functions |
| `tests/test_strategy_models.py` | Tests for each fitted model |

## Files to Modify

| File | Change |
|------|--------|
| `src/lap_coach_logger/core/stint_store.py` | Add `ThermalModel`, `WarmupModel`, `DegradationModel`, `PitProfile`, `PitMeasurement`. Update `CompoundProfile` with model fields. Update `_aggregate_profile()` to call fitting functions. Add pit profile storage. |
| `src/lap_coach_logger/core/stint_recorder.py` | Record `PitMeasurement` from pit stop telemetry. Extract per-lap `(temp, time)` pairs for model fitting. Track compound changes. |
| `src/lap_coach_logger/core/race_strategy.py` | Use `PitProfile.compute_cost()` per stop. Use `WarmupModel` for stint time. Use `DegradationModel` for stint limits. Use `ThermalModel` for condition corrections. Support timed races. |
| `src/lap_coach_logger/viewmodels/strategy_vm.py` | Add race mode toggle, duration, driver swap props. Expose model availability per compound. |
| `src/lap_coach_logger/qml/Pages/StrategyPage.qml` | Lap/timed toggle, duration input, model status indicators per compound, driver swap fields. Remove hardcoded pit time field. |
| `tests/test_stint_store.py` | Tests for pit profile, model storage. |
| `tests/test_stint_recorder.py` | Tests for pit measurement recording. |
| `tests/test_race_strategy.py` | Tests for variable pit cost, warmup, degradation, timed races. |
| `tests/test_strategy_vm.py` | Tests for race mode, model availability. |

## Out of Scope

- Monte Carlo simulation (Sub-Project B)
- Competitor modeling (Sub-Project C)
- Track evolution (Sub-Project C)
- Deep learning models (overkill — piecewise linear + exponential fits are
  sufficient given the data volumes in sim racing)
