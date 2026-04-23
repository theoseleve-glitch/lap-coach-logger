# Race Weekend Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the Strategy page into a 3-tab race weekend workflow (Practice Lab → Strategy Builder → Race Plan) with auto-capture, readiness tracking, light coaching nudges, and input-consumption correlation.

**Architecture:** New `practice_readiness.py` module computes readiness scores, nudges, input correlations, and race statistics as pure functions. `StrategyViewModel` gains auto-capture lifecycle methods and exposes readiness/nudge/correlation data to QML. `StrategyPage.qml` becomes a tabbed container with Practice, Build, and Race Plan tabs. Session lifecycle events from `DesktopService` drive auto-capture start/stop.

**Tech Stack:** Python 3.12 dataclasses, PySide6 QObject/Property/Slot, QML TabBar.

**Spec:** `docs/superpowers/specs/2026-04-12-race-weekend-workflow-design.md`

---

## Task 1: Practice Readiness Module

**Files:**
- Create: `src/lap_coach_logger/core/practice_readiness.py`
- Test: `tests/test_practice_readiness.py`

Pure functions — no dependencies on Qt, UI, or session lifecycle.

- [ ] **Step 1: Write failing tests for readiness computation**

```python
# tests/test_practice_readiness.py
"""Tests for practice readiness computation and coaching nudges."""
from __future__ import annotations

from lap_coach_logger.core.practice_readiness import (
    compute_readiness,
    compute_nudges,
)
from lap_coach_logger.core.stint_store import CompoundProfile
from lap_coach_logger.core.strategy_models import PitProfile


class TestComputeReadiness:

    def test_fully_ready_compound(self):
        profile = CompoundProfile(
            compound="soft", fuel_per_lap=2.8, fuel_curve=[2.8],
            wear_per_lap=3.0, estimated_life=18, avg_lap_time_s=90.0,
            lap_time_delta_s=0, avg_track_temp_c=30.0,
            total_laps_logged=35, stint_count=4, confidence="high",
            thermal={"available": True, "optimal_temp_low": 80, "optimal_temp_high": 95,
                     "cold_penalty_s_per_deg": 0.1, "hot_penalty_s_per_deg": 0.15,
                     "r_squared": 0.8, "sample_count": 35},
            warmup={"amplitude_s": 2.0, "decay_rate": 0.5, "raw_penalties": [2.0, 0.8],
                    "fitted": True, "sample_count": 35},
            degradation={"deg_rate_per_lap": 0.002, "cliff_lap": 16, "cliff_rate": 0.001,
                         "max_viable_stint": 18, "r_squared": 0.9, "sample_count": 35,
                         "available": True},
        )
        result = compute_readiness({"soft": profile}, None)
        assert result["soft"]["readiness_pct"] == 100
        assert result["soft"]["thermal"] is True
        assert result["soft"]["warmup"] is True
        assert result["soft"]["degradation"] is True

    def test_no_data_compound(self):
        result = compute_readiness({}, None)
        assert result == {}

    def test_partial_readiness(self):
        profile = CompoundProfile(
            compound="medium", fuel_per_lap=2.5, fuel_curve=[2.5],
            wear_per_lap=2.0, estimated_life=30, avg_lap_time_s=92.0,
            lap_time_delta_s=0, avg_track_temp_c=30.0,
            total_laps_logged=8, stint_count=1, confidence="low",
            thermal=None, warmup=None, degradation=None,
        )
        result = compute_readiness({"medium": profile}, None)
        assert result["medium"]["readiness_pct"] == 0
        assert result["medium"]["thermal"] is False


class TestComputeNudges:

    def test_nudges_for_missing_data(self):
        profiles = {
            "soft": CompoundProfile(
                compound="soft", fuel_per_lap=2.8, fuel_curve=[2.8],
                wear_per_lap=3.0, estimated_life=18, avg_lap_time_s=90.0,
                lap_time_delta_s=0, avg_track_temp_c=30.0,
                total_laps_logged=5, stint_count=1, confidence="low",
                thermal=None, warmup=None, degradation=None,
            ),
        }
        nudges = compute_nudges(profiles, None, ["soft", "medium", "hard"])
        assert any("soft" in n.lower() for n in nudges)
        assert any("medium" in n.lower() or "run" in n.lower() for n in nudges)

    def test_nudge_for_missing_pit_profile(self):
        profiles = {
            "soft": CompoundProfile(
                compound="soft", fuel_per_lap=2.8, fuel_curve=[2.8],
                wear_per_lap=3.0, estimated_life=18, avg_lap_time_s=90.0,
                lap_time_delta_s=0, avg_track_temp_c=30.0,
                total_laps_logged=35, stint_count=4, confidence="high",
                thermal={"available": True, "optimal_temp_low": 80, "optimal_temp_high": 95,
                         "cold_penalty_s_per_deg": 0.1, "hot_penalty_s_per_deg": 0.15,
                         "r_squared": 0.8, "sample_count": 35},
                warmup={"amplitude_s": 2.0, "decay_rate": 0.5, "raw_penalties": [],
                        "fitted": True, "sample_count": 35},
                degradation={"deg_rate_per_lap": 0.002, "cliff_lap": None, "cliff_rate": 0,
                             "max_viable_stint": 30, "r_squared": 0.9, "sample_count": 35,
                             "available": True},
            ),
        }
        nudges = compute_nudges(profiles, None, ["soft"])
        assert any("pit" in n.lower() for n in nudges)

    def test_race_ready_nudge(self):
        profile = CompoundProfile(
            compound="soft", fuel_per_lap=2.8, fuel_curve=[2.8],
            wear_per_lap=3.0, estimated_life=18, avg_lap_time_s=90.0,
            lap_time_delta_s=0, avg_track_temp_c=30.0,
            total_laps_logged=35, stint_count=4, confidence="high",
            thermal={"available": True, "optimal_temp_low": 80, "optimal_temp_high": 95,
                     "cold_penalty_s_per_deg": 0.1, "hot_penalty_s_per_deg": 0.15,
                     "r_squared": 0.8, "sample_count": 35},
            warmup={"amplitude_s": 2.0, "decay_rate": 0.5, "raw_penalties": [],
                    "fitted": True, "sample_count": 35},
            degradation={"deg_rate_per_lap": 0.002, "cliff_lap": None, "cliff_rate": 0,
                         "max_viable_stint": 30, "r_squared": 0.9, "sample_count": 35,
                         "available": True},
        )
        pit = PitProfile(track="Monza", beta_transit=18.0, beta_fuel_rate=0.14)
        nudges = compute_nudges({"soft": profile}, pit, ["soft"])
        assert any("ready" in n.lower() or "build" in n.lower() for n in nudges)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_practice_readiness.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement practice_readiness.py**

```python
# src/lap_coach_logger/core/practice_readiness.py
"""Practice readiness computation, coaching nudges, and input-consumption correlation.

All functions are pure — no side effects, no Qt dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lap_coach_logger.core.stint_store import CompoundProfile
from lap_coach_logger.core.strategy_models import PitProfile


def compute_readiness(
    profiles: dict[str, CompoundProfile],
    pit_profile: PitProfile | None,
) -> dict[str, dict[str, Any]]:
    """Per-compound readiness percentage and model availability."""
    result: dict[str, dict[str, Any]] = {}
    for compound, profile in profiles.items():
        has_thermal = profile.thermal is not None and profile.thermal.get("available", False)
        has_warmup = profile.warmup is not None and profile.warmup.get("fitted", False)
        has_deg = profile.degradation is not None and profile.degradation.get("available", False)
        has_confidence = profile.confidence == "high"

        score = 0
        if has_thermal:
            score += 25
        if has_warmup:
            score += 25
        if has_deg:
            score += 25
        if has_confidence:
            score += 25

        laps_for_high = max(0, 30 - profile.total_laps_logged)
        stints_for_warmup = max(0, 3 - profile.stint_count) if not has_warmup else 0

        result[compound] = {
            "readiness_pct": score,
            "thermal": has_thermal,
            "warmup": has_warmup,
            "degradation": has_deg,
            "confidence": profile.confidence,
            "total_laps_logged": profile.total_laps_logged,
            "stint_count": profile.stint_count,
            "laps_needed_for_high": laps_for_high,
            "stints_needed_for_warmup": stints_for_warmup,
        }
    return result


def compute_nudges(
    profiles: dict[str, CompoundProfile],
    pit_profile: PitProfile | None,
    available_compounds: list[str],
) -> list[str]:
    """Ordered list of actionable practice suggestions."""
    nudges: list[str] = []

    # Check for compounds with no data at all
    for compound in available_compounds:
        if compound not in profiles:
            nudges.append(f"Run at least 10 laps on {compound} tires")

    # Check existing compounds for gaps
    for compound, profile in profiles.items():
        has_thermal = profile.thermal is not None and profile.thermal.get("available", False)
        has_warmup = profile.warmup is not None and profile.warmup.get("fitted", False)
        has_deg = profile.degradation is not None and profile.degradation.get("available", False)

        if profile.confidence != "high":
            needed = max(0, 30 - profile.total_laps_logged)
            nudges.append(f"Run {needed} more laps on {compound} for high confidence")

        if not has_warmup and profile.stint_count < 3:
            needed = max(0, 3 - profile.stint_count)
            nudges.append(f"Do {needed} more full stints on {compound} (pit-to-pit)")

        if not has_thermal and profile.total_laps_logged < 5:
            needed = max(0, 5 - profile.total_laps_logged)
            nudges.append(f"Run {needed} more laps on {compound} for thermal model")

    # Pit profile
    if pit_profile is None or pit_profile.beta_transit is None:
        nudges.append("Do a pit stop to calibrate pit lane time")
    elif pit_profile.beta_fuel_rate is None:
        nudges.append("Do another pit stop with different fuel to calibrate fuel fill rate")

    # All ready?
    all_have_data = all(
        compound in profiles for compound in available_compounds if available_compounds
    )
    all_models = all(
        profiles[c].thermal is not None
        and profiles[c].warmup is not None
        and profiles[c].degradation is not None
        for c in profiles
    )
    if profiles and all_have_data and all_models and pit_profile and pit_profile.beta_transit is not None:
        nudges.append("You're race-ready! Head to Build Strategy")

    return nudges[:5]  # Cap at 5 nudges


@dataclass
class InputCorrelation:
    input_name: str
    input_value: float
    fuel_impact_l: float
    wear_impact_pct: float
    suggestion: str | None = None


def correlate_inputs_consumption(
    input_metrics: list[dict[str, Any]],
    fuel_deltas: list[float],
    wear_rates: list[float],
) -> list[InputCorrelation]:
    """Correlate driving style with fuel and tire usage.

    Each entry in input_metrics is a per-lap dict with keys like
    "throttle_aggressiveness", "brake_intensity", "smoothness".
    """
    if not input_metrics or not fuel_deltas:
        return []

    n = min(len(input_metrics), len(fuel_deltas))
    if n < 3:
        return []

    # Find the best (most efficient) lap as baseline
    best_fuel_idx = min(range(n), key=lambda i: fuel_deltas[i])
    best_fuel = fuel_deltas[best_fuel_idx]
    best_wear = wear_rates[best_fuel_idx] if best_fuel_idx < len(wear_rates) else 0.0
    best_inputs = input_metrics[best_fuel_idx]

    correlations: list[InputCorrelation] = []

    input_keys = [
        ("throttle_aggressiveness", "Throttle aggressiveness"),
        ("brake_intensity", "Trail braking intensity"),
        ("smoothness", "Cornering smoothness"),
        ("pedal_overlap", "Pedal overlap"),
    ]

    for key, label in input_keys:
        if key not in best_inputs:
            continue

        # Compare average of all laps vs best lap
        all_values = [m.get(key, 0) for m in input_metrics[:n]]
        avg_value = sum(all_values) / len(all_values) if all_values else 0

        avg_fuel = sum(fuel_deltas[:n]) / n
        fuel_impact = avg_fuel - best_fuel

        avg_wear = sum(wear_rates[:n]) / n if wear_rates else 0
        wear_impact = avg_wear - best_wear

        suggestion = None
        if key == "throttle_aggressiveness" and fuel_impact > 0.05:
            suggestion = f"Smoother throttle could save ~{fuel_impact:.2f} L/lap"
        elif key == "brake_intensity" and wear_impact > 0.5:
            suggestion = f"Lighter trail braking could reduce wear by ~{wear_impact:.1f}%/lap"
        elif key == "smoothness" and wear_impact > 0.3:
            suggestion = f"Smoother cornering could reduce wear by ~{wear_impact:.1f}%/lap"

        if abs(fuel_impact) > 0.02 or abs(wear_impact) > 0.2:
            correlations.append(InputCorrelation(
                input_name=label,
                input_value=round(avg_value, 1),
                fuel_impact_l=round(fuel_impact, 3),
                wear_impact_pct=round(wear_impact, 2),
                suggestion=suggestion,
            ))

    return correlations


def compute_race_statistics(
    plan_stints: list[dict[str, Any]],
    profiles: dict[str, CompoundProfile],
    fuel_capacity: float,
    total_race_time_s: float,
    fuel_at_finish: float,
) -> dict[str, Any]:
    """Compute race statistics from an optimized plan."""
    if not plan_stints:
        return {}

    estimated_laps = plan_stints[-1].get("end_lap", 0) if plan_stints else 0
    num_stops = max(0, len(plan_stints) - 1)

    # Qualifying target = best compound's avg lap time
    best_pace = min(
        (p.avg_lap_time_s for p in profiles.values() if p.avg_lap_time_s > 0),
        default=0,
    )

    # Race pace = weighted average across stints
    total_stint_time = sum(s.get("estimated_time_s", 0) for s in plan_stints)
    race_pace = total_stint_time / estimated_laps if estimated_laps > 0 else 0

    # Best case: -5% fuel, -10% wear (faster stints)
    best_case_time = total_race_time_s * 0.97 if total_race_time_s > 0 else 0
    # Worst case: +10% fuel, +10% wear (longer stints, extra warmup)
    worst_case_time = total_race_time_s * 1.05 if total_race_time_s > 0 else 0

    # Grip at finish from last stint
    grip_at_finish = plan_stints[-1].get("grip_at_end", 0) if plan_stints else 0

    return {
        "estimated_laps": estimated_laps,
        "estimated_race_time_s": round(total_race_time_s, 1),
        "pit_stops": num_stops,
        "qualifying_target_s": round(best_pace, 3),
        "race_pace_target_s": round(race_pace, 3),
        "best_case_time_s": round(best_case_time, 1),
        "worst_case_time_s": round(worst_case_time, 1),
        "fuel_margin_l": round(fuel_at_finish, 1),
        "grip_at_finish_pct": round(grip_at_finish, 1),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_practice_readiness.py -v`
Expected: ALL PASS

- [ ] **Step 5: Write failing tests for input correlation and race statistics**

Add to `tests/test_practice_readiness.py`:

```python
from lap_coach_logger.core.practice_readiness import (
    InputCorrelation,
    correlate_inputs_consumption,
    compute_race_statistics,
)


class TestInputCorrelation:

    def test_correlates_throttle_with_fuel(self):
        metrics = [
            {"throttle_aggressiveness": 90, "brake_intensity": 70, "smoothness": 60},
            {"throttle_aggressiveness": 85, "brake_intensity": 65, "smoothness": 65},
            {"throttle_aggressiveness": 70, "brake_intensity": 60, "smoothness": 80},  # best
        ]
        fuel = [3.2, 3.0, 2.7]
        wear = [4.0, 3.5, 3.0]

        result = correlate_inputs_consumption(metrics, fuel, wear)
        assert len(result) >= 1
        names = [r.input_name for r in result]
        assert "Throttle aggressiveness" in names

    def test_empty_inputs_returns_empty(self):
        assert correlate_inputs_consumption([], [], []) == []


class TestRaceStatistics:

    def test_computes_basic_stats(self):
        stints = [
            {"compound": "soft", "start_lap": 1, "end_lap": 15,
             "estimated_time_s": 1350.0, "grip_at_end": 45.0, "fuel_to_add": 0},
            {"compound": "medium", "start_lap": 16, "end_lap": 40,
             "estimated_time_s": 2300.0, "grip_at_end": 55.0, "fuel_to_add": 50.0},
        ]
        profiles = {
            "soft": CompoundProfile(
                compound="soft", fuel_per_lap=3.0, fuel_curve=[3.0],
                wear_per_lap=3.0, estimated_life=18, avg_lap_time_s=88.0,
                lap_time_delta_s=0, avg_track_temp_c=30.0,
                total_laps_logged=30, stint_count=3, confidence="high",
            ),
            "medium": CompoundProfile(
                compound="medium", fuel_per_lap=2.5, fuel_curve=[2.5],
                wear_per_lap=2.0, estimated_life=30, avg_lap_time_s=92.0,
                lap_time_delta_s=0, avg_track_temp_c=30.0,
                total_laps_logged=30, stint_count=3, confidence="high",
            ),
        }
        stats = compute_race_statistics(stints, profiles, 110.0, 3675.0, 4.2)
        assert stats["estimated_laps"] == 40
        assert stats["pit_stops"] == 1
        assert stats["qualifying_target_s"] == 88.0
        assert stats["fuel_margin_l"] == 4.2
        assert stats["best_case_time_s"] < stats["estimated_race_time_s"]
        assert stats["worst_case_time_s"] > stats["estimated_race_time_s"]
```

- [ ] **Step 6: Run all tests**

Run: `.venv/Scripts/python -m pytest tests/test_practice_readiness.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/lap_coach_logger/core/practice_readiness.py tests/test_practice_readiness.py
git commit -m "feat: add practice readiness computation, nudges, and input correlation"
```

---

## Task 2: Auto-Capture in StrategyViewModel

**Files:**
- Modify: `src/lap_coach_logger/viewmodels/strategy_vm.py`
- Modify: `tests/test_strategy_vm.py`

Wire automatic stint capture from session lifecycle events. Remove the manual "Record Stint" flow.

- [ ] **Step 1: Write failing tests for auto-capture lifecycle**

Add to `tests/test_strategy_vm.py`:

```python
def test_vm_on_session_detected_starts_recording(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    vm = StrategyViewModel(store=store)
    vm.on_session_detected("practice", "Monza", "GT3")
    assert vm.trackName == "Monza"
    assert vm.carName == "GT3"
    assert vm.isRecording is True


def test_vm_on_pit_detected_finalizes_stint(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    vm = StrategyViewModel(store=store)
    vm.on_session_detected("practice", "Monza", "GT3")
    # Push enough snapshots for a lap
    for i in range(3):
        vm.update_live({
            "lap_number": i + 1, "fuel_level": 50.0 - i * 3,
            "session_time_s": i * 90.0,
            "tyre_temp_lf": 85, "tyre_temp_rf": 85,
            "tyre_temp_lr": 85, "tyre_temp_rr": 85,
            "track_temp_c": 30, "air_temp_c": 22,
            "speed_kph": 200, "is_in_pits": False,
        })
    # Simulate pit entry → new stint
    vm.on_pit_detected()
    # Should still be recording (new stint started)
    assert vm.isRecording is True


def test_vm_on_session_ended_stops_recording(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    vm = StrategyViewModel(store=store)
    vm.on_session_detected("practice", "Monza", "GT3")
    vm.on_session_ended()
    assert vm.isRecording is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_strategy_vm.py -v`
Expected: FAIL — `on_session_detected` not found

- [ ] **Step 3: Implement auto-capture lifecycle methods**

Add to `StrategyViewModel`:

```python
    def on_session_detected(self, session_type: str, track: str, car: str) -> None:
        """Called when a sim session is detected. Auto-starts recording for practice/qualifying."""
        self.setTrackCar(track, car)
        if session_type in ("practice", "qualifying", "lone qualify", "open qualify"):
            self._recorder = StintRecorder(
                store=self._store, track=self._track, car=self._car,
            )
            self._recorder.start("unknown")
            self.recordingChanged.emit()

    def on_pit_detected(self) -> None:
        """Called when driver enters pit lane. Finalizes current stint, starts new one."""
        if self._recorder and self._recorder.is_recording:
            self._recorder.stop()
            self._profiles = self._store.get_profiles(self._track, self._car)
            self.profilesChanged.emit()
            self.stintLogChanged.emit()
            # Start a new stint immediately
            self._recorder = StintRecorder(
                store=self._store, track=self._track, car=self._car,
            )
            self._recorder.start("unknown")
            self.recordingChanged.emit()

    def on_session_ended(self) -> None:
        """Called when the session ends. Finalizes any active recording."""
        if self._recorder and self._recorder.is_recording:
            self._recorder.stop()
            self._profiles = self._store.get_profiles(self._track, self._car)
            self.profilesChanged.emit()
            self.stintLogChanged.emit()
        self._recorder = None
        self.recordingChanged.emit()
```

- [ ] **Step 4: Add readiness, nudges, and statistics properties**

Import at top:
```python
from lap_coach_logger.core.practice_readiness import (
    compute_nudges,
    compute_race_statistics,
    compute_readiness,
)
```

Add properties:

```python
    @Property("QVariant", notify=profilesChanged)
    def readiness(self) -> dict[str, Any]:  # noqa: N802
        pit = self._store.get_pit_profile(self._track) if self._track else None
        return compute_readiness(self._profiles, pit)

    @Property(list, notify=profilesChanged)
    def nudges(self) -> list[str]:
        pit = self._store.get_pit_profile(self._track) if self._track else None
        compounds = list(self._profiles.keys()) or ["soft", "medium", "hard"]
        return compute_nudges(self._profiles, pit, compounds)

    @Property("QVariant", notify=planChanged)
    def raceStatistics(self) -> dict[str, Any]:  # noqa: N802
        if self._plan is None:
            return {}
        return compute_race_statistics(
            self.racePlan,
            self._profiles,
            self._fuel_capacity,
            self._plan.total_race_time_s,
            self._plan.fuel_at_finish,
        )

    @Property(str, notify=planChanged)
    def activeTab(self) -> str:  # noqa: N802
        """Suggested active tab based on current state."""
        if self._plan is not None:
            return "raceplan"
        if self._profiles:
            return "build"
        return "practice"
```

- [ ] **Step 5: Update `update_live()` to detect pit transitions for auto-split**

In the existing `update_live()`, add pit detection before the recorder push:

```python
    def update_live(self, snap: dict[str, Any]) -> None:
        # Auto-detect fuel capacity
        if self._fuel_capacity <= 0:
            fuel_cap = snap.get("fuel_capacity")
            if fuel_cap is not None:
                try:
                    cap = float(fuel_cap)
                    if cap > 0:
                        self._fuel_capacity = cap
                        self.planChanged.emit()
                except (ValueError, TypeError):
                    pass

        # Auto-detect track and car
        if not self._track:
            track = snap.get("track_name")
            car = snap.get("car_name")
            if track and car:
                self.setTrackCar(str(track), str(car))

        # Auto-detect pit entry → split stints
        is_in_pits = bool(snap.get("is_in_pits", False))
        was_in_pits = getattr(self, "_was_in_pits", False)
        if is_in_pits and not was_in_pits:
            self.on_pit_detected()
        self._was_in_pits = is_in_pits

        # Feed recorder
        if self._recorder and self._recorder.is_recording:
            self._recorder.push_snapshot(snap)
            measured = self._recorder.measured_pit_time_s
            if measured is not None and abs(measured - self._pit_time) > 1.0:
                self._pit_time = round(measured, 1)
                self.planChanged.emit()
```

Add `self._was_in_pits = False` to `__init__`.

- [ ] **Step 6: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_strategy_vm.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/lap_coach_logger/viewmodels/strategy_vm.py tests/test_strategy_vm.py
git commit -m "feat: auto-capture stint recording with readiness and nudge properties"
```

---

## Task 3: Wire Session Lifecycle to StrategyViewModel

**Files:**
- Modify: `src/lap_coach_logger/qml_bootstrap.py`
- Modify: `src/lap_coach_logger/ui/desktop/service.py`

Connect DesktopService signals to the StrategyViewModel auto-capture lifecycle.

- [ ] **Step 1: Add session lifecycle signals to DesktopService**

In `src/lap_coach_logger/ui/desktop/service.py`, add a new signal and emit it when session state changes. In the `_tick()` method (where `snapshot_changed` is emitted), check `raw_state` transitions:

- When state transitions to "recording" → extract session_type, track, car from the snapshot and emit
- When state transitions to "idle" from "recording"/"ready_for_review" → session ended

Add to `DesktopService.__init__`:
```python
self._strategy_session_active = False
```

In the `_tick()` method (after building the payload dict, before `self.snapshot_changed.emit(payload)`):

```python
# Notify strategy VM of session lifecycle
if raw_state in ("arming", "recording") and not self._strategy_session_active:
    self._strategy_session_active = True
    live = payload.get("live", {})
    if hasattr(self, "_strategy_vm") and self._strategy_vm is not None:
        session_type = live.get("session_type", "practice")
        track = live.get("track_name", "")
        car = live.get("car_name", "")
        if track and car:
            self._strategy_vm.on_session_detected(str(session_type), str(track), str(car))
elif raw_state in ("idle",) and self._strategy_session_active:
    self._strategy_session_active = False
    if hasattr(self, "_strategy_vm") and self._strategy_vm is not None:
        self._strategy_vm.on_session_ended()
```

- [ ] **Step 2: Wire in qml_bootstrap.py**

In `build_view_models()`, after creating the strategy_vm and DesktopService, store a reference:

```python
service._strategy_vm = strategy_vm
```

Also connect `snapshot_changed` to feed live data:

```python
service.snapshot_changed.connect(
    lambda payload: strategy_vm.update_live(payload.get("live", {}))
)
```

- [ ] **Step 3: Verify app launches without errors**

Run: `.venv/Scripts/python -c "from lap_coach_logger.qml_bootstrap import build_view_models; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add src/lap_coach_logger/ui/desktop/service.py src/lap_coach_logger/qml_bootstrap.py
git commit -m "feat: wire session lifecycle to auto-capture in StrategyViewModel"
```

---

## Task 4: QML Strategy Page — 3-Tab Layout

**Files:**
- Modify: `src/lap_coach_logger/qml/Pages/StrategyPage.qml`

This is the biggest QML task — restructure the existing page into three tabs.

- [ ] **Step 1: Add TabBar at top of the Strategy page**

Replace the current flat layout with a TabBar + StackLayout structure. The existing content (compound profiles card, race plan timeline, stint log) moves into the Build and Race Plan tabs.

At the top of the page content Column (after the header), add:

```qml
// Tab bar
Row {
    width: parent.width
    spacing: 0

    Repeater {
        model: [
            { tabId: "practice", label: "PRACTICE" },
            { tabId: "build",    label: "BUILD" },
            { tabId: "raceplan", label: "RACE PLAN" }
        ]

        delegate: Rectangle {
            required property var modelData
            required property int index

            width: parent.width / 3
            height: 40
            color: activeTabId === modelData.tabId
                   ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.12)
                   : "transparent"

            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 2
                color: activeTabId === modelData.tabId
                       ? Theme.Tokens.pitOrange
                       : "transparent"
            }

            Text {
                anchors.centerIn: parent
                text: modelData.label
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Font.Bold
                font.letterSpacing: 1.5
                color: activeTabId === modelData.tabId
                       ? Theme.Tokens.pitOrange
                       : Theme.Tokens.steel
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: activeTabId = modelData.tabId
            }
        }
    }
}
```

Add a page-level property:
```qml
property string activeTabId: strategyVM ? strategyVM.activeTab : "practice"
```

- [ ] **Step 2: Create Practice tab content**

Wrap in a Loader or visible guard (`visible: activeTabId === "practice"`):

- **Session status bar**: green dot + "LIVE — Practice 3 · Monza · GT3 · Stint 2 · Lap 8" from strategyVM properties
- **Readiness dashboard**: Repeater over strategyVM.readiness, showing per-compound progress bar + model badges
- **Nudges card**: Repeater over strategyVM.nudges showing each as a row with → arrow
- **Driving summary card**: Pull from existing overlayVM coaching data (best lap, avg pace, consistency)
- **"Build Strategy →" button**: visible when any compound is ≥75% ready, switches to Build tab

- [ ] **Step 3: Move existing Build content into Build tab**

Take the existing compound profiles card, race parameters section (with mode toggle), and the "Auto-Optimize" button. Wrap with `visible: activeTabId === "build"`. Add "Process Strategy" button that calls `strategyVM.autoOptimize()` and switches to raceplan tab.

- [ ] **Step 4: Move Race Plan content into Race Plan tab**

Take the existing race plan timeline, stint detail rows, alerts, and stint log table. Wrap with `visible: activeTabId === "raceplan"`. Add a statistics card at the top showing data from `strategyVM.raceStatistics` (estimated laps, pace targets, best/worst case, fuel margin).

- [ ] **Step 5: Remove the manual "Record Stint" button**

The header buttons change to: "Build Strategy →" and "Auto-Optimize" (context-dependent on tab). Remove the manual Record Stint / Stop Recording button since capture is now automatic.

- [ ] **Step 6: Verify app launches and tabs work**

Run: `start "" .venv/Scripts/pythonw.exe -m lap_coach_logger`
Click Strategy in nav. Verify 3 tabs load. Switch between them.

- [ ] **Step 7: Commit**

```bash
git add src/lap_coach_logger/qml/Pages/StrategyPage.qml
git commit -m "feat: restructure Strategy page into Practice/Build/Race Plan tabs"
```

---

## Task 5: Final Integration Test

**Files:** All modified files

- [ ] **Step 1: Run full test suite**

Run: `.venv/Scripts/python -m pytest tests/ -q --tb=short --ignore=tests/test_desktop_workspaces.py --ignore=tests/test_ghost_widget.py --ignore=tests/test_overlay_browser_frontend.py --ignore=tests/test_overlay_window_manager.py`
Expected: ALL PASS

- [ ] **Step 2: Run Qt widget tests separately**

Run: `.venv/Scripts/python -m pytest tests/test_desktop_workspaces.py tests/test_ghost_widget.py tests/test_overlay_browser_frontend.py tests/test_overlay_window_manager.py -q`
Expected: ALL PASS

- [ ] **Step 3: Launch app and verify workflow**

Run: `start "" .venv/Scripts/pythonw.exe -m lap_coach_logger`

Verify:
1. Strategy page shows 3 tabs: PRACTICE | BUILD | RACE PLAN
2. Practice tab shows readiness dashboard (empty compounds = "No data")
3. Practice tab shows nudges ("Run at least 10 laps on soft tires")
4. Build tab shows compound profiles + race parameters
5. Race Plan tab shows plan after optimizing
6. Switching tabs works

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: race weekend workflow complete — Practice/Build/Race Plan"
```
