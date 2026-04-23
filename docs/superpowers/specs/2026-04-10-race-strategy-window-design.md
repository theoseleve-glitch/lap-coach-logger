# Race Strategy Window — Design Spec

## Overview

A dedicated Race Strategy page in the main app with weather-aware pit planning,
per-compound stint profiles built from aggregated telemetry data, and live
mid-race recalculation. The existing overlay widget becomes a compact live
readout fed by the same strategy engine.

## Goals

1. Let the driver build a pit strategy from real data, not guesswork.
2. Accumulate stint data across sessions — more laps logged = higher confidence.
3. Auto-optimize compound order and stint lengths using logged profiles.
4. Recalculate the plan live during the race as conditions change.
5. Surface weather forecasts (iRacing) and adjust strategy proactively.

## Layout

**Top-Down Flow** (Layout A from brainstorm):

```
┌──────────────────────────────────────────────────────┐
│ Dashboard │ Live │ ▶ Strategy │ History │ Settings   │  ← nav bar
├──────────────────────────────────────────────────────┤
│                                                      │
│  Race Strategy                                       │
│  Monza · Ferrari 296 GT3 · 45 laps                   │
│                         [Import Stint] [Record] [Auto]│
│                                                      │
│  ┌─ COMPOUND PROFILES ────────────────────────────┐  │
│  │ ● SOFT   2.81 L/lap · 3.2%/lap · ~18 laps     │  │
│  │          43 laps logged · high confidence       │  │
│  │ ● MED    2.58 L/lap · 1.8%/lap · ~32 laps     │  │
│  │          25 laps logged · medium confidence     │  │
│  │ ● HARD   no data                               │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌─ RACE PLAN — 45 LAPS · 1 STOP ────────────────┐  │
│  │ ▓▓▓▓▓▓▓ SOFT L1-18 ▓▓▓▓▓▓▓│░░░░░ MED L19-45 │  │
│  │ Pit Lap 18 · +52.4L · Est 1:12:34 · +4.2L fin │  │
│  │                                                │  │
│  │ ⚡ Weather: Rain prob 60% at ~Lap 22           │  │
│  │   Consider pit Lap 15 → Wets (saves 1 stop)   │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌─ LOGGED STINTS ────────────────────────────────┐  │
│  │ Qualifying  SOFT  18 laps  2.81 L  3.2%  ● Act │  │
│  │ Practice 3  MED   25 laps  2.58 L  1.8%  ● Act │  │
│  │ Practice 1  SOFT  12 laps  3.10 L  3.5%  ● Act │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## Components

### 1. StintStore (`src/lap_coach_logger/core/stint_store.py`)

JSON-based persistence at `%LOCALAPPDATA%\LapCoachLogger\runtime\stint_profiles.json`.

**StintRecord** — one logged stint:

| Field | Type | Description |
|-------|------|-------------|
| id | str | UUID |
| compound | str | "soft" / "medium" / "hard" / "wet" / "inter" |
| fuel_per_lap_series | list[float] | Per-lap fuel deltas (not just average) |
| fuel_per_lap | float | Weighted average fuel consumption |
| wear_per_lap | float | Grip % lost per lap (average) |
| grip_at_end | float | Grip % when stint ended |
| lap_count | int | Number of laps in the stint |
| avg_lap_time_s | float | Average lap time |
| track_temp_c | float | Average track temp during stint |
| air_temp_c | float | Average air temp during stint |
| source_session_id | str | Session bundle folder name |
| source_label | str | Human label ("Practice 3", "Qualifying") |
| recorded_at | str | ISO timestamp |
| excluded | bool | False by default; True if user marks as bad data |

**Store structure** — keyed by `"track::car"`:

```json
{
  "Monza::Ferrari 296 GT3": [
    { "id": "...", "compound": "soft", "fuel_per_lap": 2.81, ... },
    { "id": "...", "compound": "soft", "fuel_per_lap": 3.10, ... }
  ]
}
```

**CompoundProfile** — aggregated from all non-excluded stints of the same compound:

| Field | Type | Description |
|-------|------|-------------|
| compound | str | Compound name |
| fuel_per_lap | float | Weighted average (weight = lap_count) |
| fuel_curve | list[float] | Aggregated per-lap fuel curve |
| wear_per_lap | float | Weighted average wear rate |
| estimated_life | int | Laps before grip < threshold |
| avg_lap_time_s | float | Weighted average lap time |
| lap_time_delta_s | float | Delta vs. baseline compound |
| avg_track_temp_c | float | Average conditions across stints |
| total_laps_logged | int | Sum of all contributing stint lap counts |
| stint_count | int | Number of stints that contributed |
| confidence | str | "low" (<10 laps) / "medium" (10-30) / "high" (30+) |

**Public API:**

- `log_stint(track, car, record: StintRecord)` — add a stint
- `get_profiles(track, car) -> dict[str, CompoundProfile]` — aggregated profiles
- `list_stints(track, car) -> list[StintRecord]` — all stints, newest first
- `exclude_stint(stint_id)` / `include_stint(stint_id)` — toggle exclusion
- `import_from_session(session_path, compound) -> StintRecord` — extract from saved session
- `clear(track, car)` — remove all stints for a track+car combo

### 2. StintRecorder (`src/lap_coach_logger/core/stint_recorder.py`)

Captures a reference stint from live telemetry.

**State machine:** `IDLE → RECORDING → FINALIZING → IDLE`

**During recording**, each telemetry sample is processed:
- Fuel level tracked per lap (delta = consumption)
- Tire temps fed to the existing `TireDegradationTracker`
- Track/air temp accumulated for averaging
- Lap times recorded

**On stop** (or session end):
- Computes `StintRecord` from accumulated data
- Calls `StintStore.log_stint()`
- Returns the record for UI confirmation

**Auto-recording:** When a race session starts and a strategy plan exists,
the recorder starts automatically. The completed race stint is logged to the
store on session finalization (post-race data for future strategy).

### 3. Enhanced Race Strategy Engine (extend `race_strategy.py`)

**New inputs:**

```python
@dataclass
class CompoundProfile:
    compound: str
    fuel_per_lap: float
    fuel_curve: list[float]       # per-lap consumption curve
    wear_per_lap: float
    estimated_life: int
    avg_lap_time_s: float
    lap_time_delta_s: float
    avg_track_temp_c: float

@dataclass
class ConditionWindow:
    start_lap: int
    end_lap: int
    track_temp_c: float
    precipitation: float          # 0.0 = dry, 1.0 = heavy rain
    track_state: str              # "dry" / "damp" / "wet"
    recommended_compound: str     # "soft"/"wet"/etc based on conditions
```

**New functions:**

- `optimize_strategy(total_laps, fuel_capacity, pit_time_s, profiles, conditions=None) -> RacePlan`
  - Tries valid compound orderings (respecting mandatory compound rules if configured)
  - Uses per-lap fuel curves instead of flat averages
  - Applies temperature correction to wear/fuel rates based on condition windows
  - Picks the combination with lowest total race time
  - Returns a `RacePlan` with ordered stints + pit windows

- `recalculate_live(plan, current_lap, current_fuel, actual_fuel_deltas, actual_wear, current_conditions) -> RacePlan`
  - Compares actual per-lap fuel burn to the plan's fuel curve
  - Compares actual tire wear to planned degradation
  - Factors in current weather/track state
  - Returns updated plan with shifted pit windows and alerts

**RacePlan** (replaces current `RaceStrategy`):

| Field | Type | Description |
|-------|------|-------------|
| stints | list[PlannedStint] | Ordered stint list |
| total_race_time_s | float | Estimated total time |
| fuel_at_finish | float | Predicted remaining fuel |
| alerts | list[StrategyAlert] | Active warnings/suggestions |

**PlannedStint:**

| Field | Type | Description |
|-------|------|-------------|
| compound | str | Tire compound for this stint |
| start_lap | int | First lap of stint |
| end_lap | int | Last lap of stint (= pit lap) |
| fuel_at_start | float | Predicted fuel level |
| fuel_to_add | float | Fuel to add at preceding pit stop (0 for first stint) |
| grip_at_end | float | Predicted grip % at end of stint |
| estimated_time_s | float | Estimated stint duration |

**StrategyAlert:**

| Field | Type | Description |
|-------|------|-------------|
| severity | str | "info" / "warning" / "critical" |
| category | str | "fuel" / "tire" / "weather" / "divergence" |
| message | str | Human-readable alert text |
| suggested_action | str or None | e.g. "Pit now" / "Extend 3 laps" |

### 4. Weather Monitor (`src/lap_coach_logger/core/strategy_weather.py`)

iRacing-specific module. Clean interface so non-iRacing sims skip it.

**Input:** iRacing session info `WeatherForecast[]` array + live telemetry
channels (`Precipitation`, `TrackWetness`, `TrackTempCrew`, `AirTemp`,
`WindVel`, `WindDir`).

**Output:** `list[ConditionWindow]` — a timeline of predicted conditions
mapped to lap numbers.

**Functions:**

- `parse_forecast(session_info, lap_time_s, total_laps) -> list[ConditionWindow]`
  - Reads `WeatherForecast` entries from session info YAML
  - Converts time-based forecast to lap-based windows using average lap time
  - Classifies each window: dry / damp / wet / heavy
  - Recommends compound per window (dry→slick, damp→inter, wet→wet)

- `update_from_live(current_windows, precipitation, track_wetness, track_temp, current_lap) -> list[ConditionWindow]`
  - Adjusts forecast based on actual conditions
  - If rain arrives earlier/later than forecast, shifts remaining windows
  - Returns updated condition timeline

**Temperature correction** (all sims, not just iRacing):

When stint data was logged at a different track temp than current conditions:
- Fuel correction: ±0.3% per °C delta (hotter = slightly more fuel)
- Wear correction: ±0.5% per °C delta (hotter = faster wear)
- These factors are conservative defaults; the aggregation across multiple
  stints at different temps naturally captures the real correlation.

### 5. StrategyViewModel (`src/lap_coach_logger/viewmodels/strategy_vm.py`)

QObject bridging the strategy engine to QML.

**Properties (read from QML):**

| Property | Type | Description |
|----------|------|-------------|
| trackName | str | Current track |
| carName | str | Current car |
| totalLaps | int | Race length |
| compoundProfiles | list | Aggregated profiles for QML display |
| racePlan | list | Ordered stints with pit windows |
| stintLog | list | All logged stints for this track+car |
| alerts | list | Active strategy alerts |
| isRecording | bool | Stint recorder active |
| hasWeatherData | bool | Weather forecast available |
| weatherTimeline | list | Condition windows for display |
| fuelCapacity | float | Tank size |
| pitTime | float | Pit lane time loss |
| planDiverged | bool | Actual vs. plan has significant drift |

**Slots (called from QML):**

| Slot | Description |
|------|-------------|
| importStint(sessionPath, compound) | Extract stint from saved session |
| startRecording(compound) | Begin live stint capture |
| stopRecording() | End capture, log to store |
| autoOptimize() | Run optimizer with current profiles |
| setTotalLaps(n) | Update race length |
| setFuelCapacity(v) | Update tank size |
| setPitTime(v) | Update pit lane delta |
| editStintLaps(index, laps) | Manually adjust a stint's length |
| addStint(compound) | Append a stint to the plan |
| removeStint(index) | Remove a stint from the plan |
| moveStint(fromIndex, toIndex) | Reorder stints |
| excludeLoggedStint(stintId) | Mark a logged stint as excluded |
| includeLoggedStint(stintId) | Re-include a logged stint |
| clearStints() | Remove all logged stints for this track+car |

### 6. QML Strategy Page (`src/lap_coach_logger/qml/Pages/StrategyPage.qml`)

New page registered in `AppShell.qml` nav bar between Live and History.

**Sections (top-down):**

1. **Header** — page title, track+car subtitle (auto-populated from current/last
   session), action buttons (Import Stint, Record Stint, Auto-Optimize)

2. **Compound Profiles** — card showing each compound with aggregated stats,
   confidence level, and total laps logged. Compounds with no data show
   "no data logged" in muted text.

3. **Race Plan** — colored timeline bar showing stint blocks (soft=red,
   medium=yellow, hard=white, wet=blue, inter=green). Below the bar: pit lap,
   fuel to add, estimated race time, fuel at finish, tire grip at finish.
   Weather alerts shown inline if forecast data available. Stints are
   clickable to edit length. "+ Add stint" at the end.

4. **Weather Forecast** (iRacing only, hidden otherwise) — condition timeline
   showing temperature curve and rain probability mapped to laps. Updates
   live during race.

5. **Logged Stints** — table of all recorded stints for this track+car.
   Columns: session label, compound, laps, fuel/lap, wear/lap, grip at end,
   track temp, status (active/excluded). Click to exclude/include.

### 7. Overlay Integration

The existing `RaceStrategyWidget` QML overlay (280x200) and `FuelCalculatorWidget`
already read strategy data from the `OverlayViewModel`. With this feature:

- `OverlayViewModel` gains a reference to `StrategyViewModel`
- Strategy properties (next pit lap, fuel to add, alerts) flow from
  `StrategyViewModel` → `OverlayViewModel` → overlay widgets
- No new overlay window needed — the existing widgets become smarter
- Weather alerts surface as a one-line badge in the strategy overlay:
  "🌧 Rain ~Lap 22 — pit early"

### 8. Live Race Flow

1. **Pre-race:** User sets up strategy on Strategy page. Optimizer runs
   with logged profiles + weather forecast (if iRacing). Plan is ready.

2. **Race start:** `StrategyViewModel` enters live mode. `StintRecorder`
   starts automatically. Weather monitor begins polling.

3. **Each lap:** Engine compares actual fuel delta and wear to plan.
   If divergence exceeds threshold (configurable), plan auto-recalculates.
   Alerts surface in overlay + Strategy page.

4. **Weather change:** `WeatherMonitor` detects precipitation or forecast
   update. Strategy recalculates with new condition windows. Alert:
   "Rain starting — pit window moved to Lap 15."

5. **Pit stop:** When driver pits, engine detects position/speed entering
   pit lane. Marks current stint as complete. Starts tracking next stint.

6. **Race end:** Final stint auto-logged to `StintStore`. Strategy page
   shows post-race summary (planned vs. actual).

### 9. Session Import Flow

When user clicks "Import Stint" and selects a saved session:

1. Read `session.json` for track name, car name, session type, duration.
2. Read `laps.json` for per-lap timing data.
3. Read telemetry file (parquet or csv) for:
   - `fuel_level` column → compute per-lap deltas
   - `tyre_temp_*` columns → compute per-lap averages → wear estimation
   - `track_temp_c`, `air_temp_c` → average conditions
4. User selects compound (or auto-detect if sim provides it).
5. User can trim the stint (e.g., "use laps 3-18, skip outlap and cooldown").
6. `StintRecord` created and added to store.
7. Compound profiles recomputed with new data.

## Files to Create

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `src/lap_coach_logger/core/stint_store.py` | ~250 | Stint persistence + aggregation |
| `src/lap_coach_logger/core/stint_recorder.py` | ~200 | Live stint capture |
| `src/lap_coach_logger/core/strategy_weather.py` | ~200 | iRacing weather forecast parsing |
| `src/lap_coach_logger/viewmodels/strategy_vm.py` | ~400 | QML ViewModel |
| `src/lap_coach_logger/qml/Pages/StrategyPage.qml` | ~350 | Strategy page UI |
| `tests/test_stint_store.py` | ~200 | Store + aggregation tests |
| `tests/test_stint_recorder.py` | ~150 | Recorder tests |
| `tests/test_strategy_weather.py` | ~150 | Weather parsing tests |
| `tests/test_strategy_vm.py` | ~150 | ViewModel tests |

## Files to Modify

| File | Change |
|------|--------|
| `src/lap_coach_logger/core/race_strategy.py` | Add `CompoundProfile`, `ConditionWindow`, `RacePlan`, `optimize_strategy()`, enhanced `recalculate_live()` |
| `src/lap_coach_logger/core/tire_model.py` | Add `wear_from_stint()` to extract wear data from telemetry |
| `src/lap_coach_logger/viewmodels/overlay_vm.py` | Wire strategy properties from `StrategyViewModel` |
| `src/lap_coach_logger/qml/AppShell.qml` | Add Strategy nav item + page loader |
| `src/lap_coach_logger/qml/Overlay/widgets/RaceStrategyWidget.qml` | Add weather alert badge, use fuel curve data |
| `src/lap_coach_logger/qml_bootstrap.py` | Create `StrategyViewModel`, register as context property |
| `src/lap_coach_logger/bootstrap.py` | Initialize `StintStore` |
| `src/lap_coach_logger/adapters/iracing_adapter.py` | Expose weather forecast from session info |

## Out of Scope (v1)

- Traffic / dirty air fuel correction (needs position/gap channels — v2)
- Tire pressure modeling
- Multi-driver stint planning (endurance relay)
- Cloud sync of stint profiles
- Drag-to-reorder stints in the timeline (edit length only for v1)
