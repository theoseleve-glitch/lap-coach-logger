# Race Strategy Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated Strategy page with per-compound stint profiles, weather-aware pit planning, and live mid-race recalculation.

**Architecture:** Data flows bottom-up: `StintStore` (JSON persistence) → `CompoundProfile` aggregation → `RaceStrategy` engine (optimization + live recalc) → `StrategyViewModel` (QObject) → QML Strategy page + existing overlay widgets. Weather data is iRacing-specific via `strategy_weather.py`. `StintRecorder` captures stints from live telemetry and writes to the store.

**Tech Stack:** Python 3.12 dataclasses, JSON persistence, PySide6 QObject/Signal/Property/Slot, QML (Qt Quick), pyarrow for parquet reads during session import.

**Spec:** `docs/superpowers/specs/2026-04-10-race-strategy-window-design.md`

---

## Task 1: StintStore — Data Model and Persistence

**Files:**
- Create: `src/lap_coach_logger/core/stint_store.py`
- Test: `tests/test_stint_store.py`

- [ ] **Step 1: Write failing test — StintRecord dataclass**

```python
# tests/test_stint_store.py
"""Tests for stint profile persistence and compound aggregation."""
from __future__ import annotations

import json
from pathlib import Path

from lap_coach_logger.core.stint_store import StintRecord, StintStore


def test_stint_record_roundtrips_to_dict():
    record = StintRecord(
        compound="soft",
        fuel_per_lap=2.81,
        fuel_per_lap_series=[3.1, 2.9, 2.8, 2.7, 2.75],
        wear_per_lap=3.2,
        grip_at_end=42.0,
        lap_count=5,
        avg_lap_time_s=91.5,
        track_temp_c=32.0,
        air_temp_c=24.0,
        source_session_id="2026-01-01_00-00-00__iRacing__Monza__Race",
        source_label="Practice 3",
    )
    d = record.to_dict()
    restored = StintRecord.from_dict(d)
    assert restored.compound == "soft"
    assert restored.fuel_per_lap == 2.81
    assert restored.lap_count == 5
    assert restored.id  # UUID auto-generated
    assert restored.excluded is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_stint_store.py::test_stint_record_roundtrips_to_dict -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lap_coach_logger.core.stint_store'`

- [ ] **Step 3: Implement StintRecord dataclass**

```python
# src/lap_coach_logger/core/stint_store.py
"""Stint profile persistence and per-compound aggregation.

Stores logged stints keyed by track+car. Aggregates all non-excluded
stints of the same compound into a CompoundProfile using weighted
averages (weight = lap_count).
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class StintRecord:
    compound: str
    fuel_per_lap: float
    fuel_per_lap_series: list[float]
    wear_per_lap: float
    grip_at_end: float
    lap_count: int
    avg_lap_time_s: float
    track_temp_c: float
    air_temp_c: float
    source_session_id: str
    source_label: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    excluded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "compound": self.compound,
            "fuel_per_lap": self.fuel_per_lap,
            "fuel_per_lap_series": list(self.fuel_per_lap_series),
            "wear_per_lap": self.wear_per_lap,
            "grip_at_end": self.grip_at_end,
            "lap_count": self.lap_count,
            "avg_lap_time_s": self.avg_lap_time_s,
            "track_temp_c": self.track_temp_c,
            "air_temp_c": self.air_temp_c,
            "source_session_id": self.source_session_id,
            "source_label": self.source_label,
            "recorded_at": self.recorded_at,
            "excluded": self.excluded,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StintRecord:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            compound=data["compound"],
            fuel_per_lap=data["fuel_per_lap"],
            fuel_per_lap_series=data.get("fuel_per_lap_series", []),
            wear_per_lap=data["wear_per_lap"],
            grip_at_end=data["grip_at_end"],
            lap_count=data["lap_count"],
            avg_lap_time_s=data["avg_lap_time_s"],
            track_temp_c=data.get("track_temp_c", 0.0),
            air_temp_c=data.get("air_temp_c", 0.0),
            source_session_id=data.get("source_session_id", ""),
            source_label=data.get("source_label", ""),
            recorded_at=data.get("recorded_at", ""),
            excluded=data.get("excluded", False),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_stint_store.py::test_stint_record_roundtrips_to_dict -v`
Expected: PASS

- [ ] **Step 5: Write failing test — StintStore log and list**

Add to `tests/test_stint_store.py`:

```python
def test_store_log_and_list(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    record = StintRecord(
        compound="soft",
        fuel_per_lap=2.81,
        fuel_per_lap_series=[2.9, 2.8],
        wear_per_lap=3.2,
        grip_at_end=42.0,
        lap_count=2,
        avg_lap_time_s=91.5,
        track_temp_c=32.0,
        air_temp_c=24.0,
        source_session_id="session-1",
        source_label="Practice 1",
    )
    store.log_stint("Monza", "Ferrari 296 GT3", record)
    stints = store.list_stints("Monza", "Ferrari 296 GT3")
    assert len(stints) == 1
    assert stints[0].compound == "soft"
    # Persisted to disk
    assert (tmp_path / "stints.json").exists()
    # Reload from disk
    store2 = StintStore(tmp_path / "stints.json")
    assert len(store2.list_stints("Monza", "Ferrari 296 GT3")) == 1
```

- [ ] **Step 6: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_stint_store.py::test_store_log_and_list -v`
Expected: FAIL — `StintStore` not defined

- [ ] **Step 7: Implement StintStore**

Add to `src/lap_coach_logger/core/stint_store.py`:

```python
def _store_key(track: str, car: str) -> str:
    return f"{track}::{car}"


class StintStore:
    """Persists stint records and computes aggregated compound profiles."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, list[dict[str, Any]]] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                log.warning("Failed to load stint store", exc_info=True)
                self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, indent=2), encoding="utf-8"
        )

    def log_stint(self, track: str, car: str, record: StintRecord) -> None:
        key = _store_key(track, car)
        if key not in self._data:
            self._data[key] = []
        self._data[key].insert(0, record.to_dict())
        self._save()

    def list_stints(self, track: str, car: str) -> list[StintRecord]:
        key = _store_key(track, car)
        return [StintRecord.from_dict(d) for d in self._data.get(key, [])]

    def exclude_stint(self, stint_id: str) -> None:
        self._set_excluded(stint_id, True)

    def include_stint(self, stint_id: str) -> None:
        self._set_excluded(stint_id, False)

    def _set_excluded(self, stint_id: str, excluded: bool) -> None:
        for records in self._data.values():
            for rec in records:
                if rec.get("id") == stint_id:
                    rec["excluded"] = excluded
                    self._save()
                    return

    def clear(self, track: str, car: str) -> None:
        key = _store_key(track, car)
        self._data.pop(key, None)
        self._save()
```

- [ ] **Step 8: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_stint_store.py -v`
Expected: 2 PASS

- [ ] **Step 9: Write failing test — CompoundProfile aggregation**

Add to `tests/test_stint_store.py`:

```python
from lap_coach_logger.core.stint_store import CompoundProfile


def test_get_profiles_aggregates_by_compound(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    # Two soft stints with different data
    store.log_stint("Monza", "GT3", StintRecord(
        compound="soft", fuel_per_lap=2.8, fuel_per_lap_series=[2.9, 2.7],
        wear_per_lap=3.0, grip_at_end=45.0, lap_count=2,
        avg_lap_time_s=90.0, track_temp_c=30.0, air_temp_c=22.0,
        source_session_id="s1", source_label="P1",
    ))
    store.log_stint("Monza", "GT3", StintRecord(
        compound="soft", fuel_per_lap=2.6, fuel_per_lap_series=[2.7, 2.6, 2.5],
        wear_per_lap=2.8, grip_at_end=50.0, lap_count=3,
        avg_lap_time_s=89.0, track_temp_c=28.0, air_temp_c=21.0,
        source_session_id="s2", source_label="P2",
    ))
    profiles = store.get_profiles("Monza", "GT3")
    assert "soft" in profiles
    p = profiles["soft"]
    assert p.total_laps_logged == 5
    assert p.stint_count == 2
    # Weighted average: (2.8*2 + 2.6*3) / 5 = 2.68
    assert abs(p.fuel_per_lap - 2.68) < 0.01
    assert p.confidence == "low"  # <10 laps


def test_excluded_stints_are_not_aggregated(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    r1 = StintRecord(
        compound="medium", fuel_per_lap=2.5, fuel_per_lap_series=[2.5],
        wear_per_lap=1.8, grip_at_end=60.0, lap_count=1,
        avg_lap_time_s=92.0, track_temp_c=30.0, air_temp_c=22.0,
        source_session_id="s1", source_label="P1",
    )
    store.log_stint("Monza", "GT3", r1)
    store.exclude_stint(r1.id)
    profiles = store.get_profiles("Monza", "GT3")
    assert "medium" not in profiles  # excluded → no profile
```

- [ ] **Step 10: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_stint_store.py -v`
Expected: FAIL — `CompoundProfile` not defined

- [ ] **Step 11: Implement CompoundProfile and get_profiles()**

Add to `src/lap_coach_logger/core/stint_store.py`, after `StintRecord`:

```python
@dataclass
class CompoundProfile:
    compound: str
    fuel_per_lap: float
    fuel_curve: list[float]
    wear_per_lap: float
    estimated_life: int
    avg_lap_time_s: float
    lap_time_delta_s: float
    avg_track_temp_c: float
    total_laps_logged: int
    stint_count: int
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "compound": self.compound,
            "fuel_per_lap": round(self.fuel_per_lap, 3),
            "fuel_curve": [round(v, 3) for v in self.fuel_curve],
            "wear_per_lap": round(self.wear_per_lap, 2),
            "estimated_life": self.estimated_life,
            "avg_lap_time_s": round(self.avg_lap_time_s, 3),
            "lap_time_delta_s": round(self.lap_time_delta_s, 3),
            "avg_track_temp_c": round(self.avg_track_temp_c, 1),
            "total_laps_logged": self.total_laps_logged,
            "stint_count": self.stint_count,
            "confidence": self.confidence,
        }
```

Add `get_profiles` method to `StintStore`:

```python
    def get_profiles(self, track: str, car: str) -> dict[str, CompoundProfile]:
        stints = [s for s in self.list_stints(track, car) if not s.excluded]
        compounds: dict[str, list[StintRecord]] = {}
        for s in stints:
            compounds.setdefault(s.compound, []).append(s)

        profiles: dict[str, CompoundProfile] = {}
        for compound, records in compounds.items():
            profiles[compound] = _aggregate_profile(compound, records)
        return profiles


def _aggregate_profile(compound: str, records: list[StintRecord]) -> CompoundProfile:
    total_laps = sum(r.lap_count for r in records)
    if total_laps == 0:
        return CompoundProfile(
            compound=compound, fuel_per_lap=0, fuel_curve=[], wear_per_lap=0,
            estimated_life=0, avg_lap_time_s=0, lap_time_delta_s=0,
            avg_track_temp_c=0, total_laps_logged=0, stint_count=0, confidence="low",
        )

    fuel_per_lap = sum(r.fuel_per_lap * r.lap_count for r in records) / total_laps
    wear_per_lap = sum(r.wear_per_lap * r.lap_count for r in records) / total_laps
    avg_lap_time = sum(r.avg_lap_time_s * r.lap_count for r in records) / total_laps
    avg_track_temp = sum(r.track_temp_c * r.lap_count for r in records) / total_laps

    # Build aggregated fuel curve: average per-lap deltas across stints
    max_len = max((len(r.fuel_per_lap_series) for r in records), default=0)
    fuel_curve: list[float] = []
    for i in range(max_len):
        values = [r.fuel_per_lap_series[i] for r in records if i < len(r.fuel_per_lap_series)]
        fuel_curve.append(sum(values) / len(values) if values else fuel_per_lap)

    grip_threshold = 40.0
    estimated_life = int((100.0 - grip_threshold) / max(0.1, wear_per_lap))

    if total_laps < 10:
        confidence = "low"
    elif total_laps < 30:
        confidence = "medium"
    else:
        confidence = "high"

    return CompoundProfile(
        compound=compound,
        fuel_per_lap=fuel_per_lap,
        fuel_curve=fuel_curve,
        wear_per_lap=wear_per_lap,
        estimated_life=estimated_life,
        avg_lap_time_s=avg_lap_time,
        lap_time_delta_s=0.0,
        avg_track_temp_c=avg_track_temp,
        total_laps_logged=total_laps,
        stint_count=len(records),
        confidence=confidence,
    )
```

- [ ] **Step 12: Run all stint store tests**

Run: `.venv/Scripts/python -m pytest tests/test_stint_store.py -v`
Expected: 4 PASS

- [ ] **Step 13: Commit**

```bash
git add src/lap_coach_logger/core/stint_store.py tests/test_stint_store.py
git commit -m "feat: add StintStore with per-compound aggregation"
```

---

## Task 2: Enhanced Race Strategy Engine

**Files:**
- Modify: `src/lap_coach_logger/core/race_strategy.py`
- Test: `tests/test_race_strategy.py`

- [ ] **Step 1: Write failing test — RacePlan + optimize_strategy**

Add to `tests/test_race_strategy.py`:

```python
from lap_coach_logger.core.stint_store import CompoundProfile
from lap_coach_logger.core.race_strategy import (
    RacePlan, PlannedStint, StrategyAlert,
    optimize_strategy,
)


def test_optimize_single_compound_no_stop():
    soft = CompoundProfile(
        compound="soft", fuel_per_lap=2.5, fuel_curve=[2.5],
        wear_per_lap=2.0, estimated_life=30, avg_lap_time_s=90.0,
        lap_time_delta_s=0.0, avg_track_temp_c=30.0,
        total_laps_logged=20, stint_count=2, confidence="medium",
    )
    plan = optimize_strategy(
        total_laps=20, fuel_capacity=60.0, pit_time_s=25.0,
        profiles={"soft": soft},
    )
    assert isinstance(plan, RacePlan)
    assert len(plan.stints) == 1
    assert plan.stints[0].compound == "soft"
    assert plan.stints[0].start_lap == 1
    assert plan.stints[0].end_lap == 20
    assert plan.fuel_at_finish > 0


def test_optimize_two_compounds_picks_fastest():
    soft = CompoundProfile(
        compound="soft", fuel_per_lap=3.0, fuel_curve=[3.0],
        wear_per_lap=4.0, estimated_life=15, avg_lap_time_s=88.0,
        lap_time_delta_s=-2.0, avg_track_temp_c=30.0,
        total_laps_logged=30, stint_count=3, confidence="high",
    )
    medium = CompoundProfile(
        compound="medium", fuel_per_lap=2.5, fuel_curve=[2.5],
        wear_per_lap=2.0, estimated_life=30, avg_lap_time_s=90.0,
        lap_time_delta_s=0.0, avg_track_temp_c=30.0,
        total_laps_logged=30, stint_count=3, confidence="high",
    )
    plan = optimize_strategy(
        total_laps=40, fuel_capacity=100.0, pit_time_s=25.0,
        profiles={"soft": soft, "medium": medium},
    )
    assert isinstance(plan, RacePlan)
    assert len(plan.stints) >= 2
    compounds_used = {s.compound for s in plan.stints}
    assert len(compounds_used) >= 1  # optimizer chose at least one
    assert plan.total_race_time_s > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_race_strategy.py::test_optimize_single_compound_no_stop -v`
Expected: FAIL — `RacePlan` not importable

- [ ] **Step 3: Implement new dataclasses and optimize_strategy**

Add to `src/lap_coach_logger/core/race_strategy.py` (after existing code):

```python
from lap_coach_logger.core.stint_store import CompoundProfile


@dataclass
class PlannedStint:
    compound: str
    start_lap: int
    end_lap: int
    fuel_at_start: float
    fuel_to_add: float
    grip_at_end: float
    estimated_time_s: float


@dataclass
class StrategyAlert:
    severity: str       # "info" / "warning" / "critical"
    category: str       # "fuel" / "tire" / "weather" / "divergence"
    message: str
    suggested_action: str | None = None


@dataclass
class RacePlan:
    stints: list[PlannedStint]
    total_race_time_s: float
    fuel_at_finish: float
    alerts: list[StrategyAlert] = field(default_factory=list)

    @property
    def num_stops(self) -> int:
        return max(0, len(self.stints) - 1)

    @property
    def next_pit_lap(self) -> int:
        if len(self.stints) < 2:
            return 0
        return self.stints[0].end_lap


@dataclass
class ConditionWindow:
    start_lap: int
    end_lap: int
    track_temp_c: float
    precipitation: float
    track_state: str
    recommended_compound: str


def _fuel_for_laps(profile: CompoundProfile, n_laps: int) -> float:
    """Sum fuel using the per-lap curve, extending with the flat average."""
    total = 0.0
    for i in range(n_laps):
        if i < len(profile.fuel_curve):
            total += profile.fuel_curve[i]
        else:
            total += profile.fuel_per_lap
    return total


def _apply_temp_correction(
    profile: CompoundProfile, track_temp_c: float
) -> tuple[float, float]:
    """Return (corrected_fuel_per_lap, corrected_wear_per_lap)."""
    if profile.avg_track_temp_c <= 0:
        return profile.fuel_per_lap, profile.wear_per_lap
    delta = track_temp_c - profile.avg_track_temp_c
    fuel = profile.fuel_per_lap * (1.0 + delta * 0.003)
    wear = profile.wear_per_lap * (1.0 + delta * 0.005)
    return fuel, wear


def _build_single_compound_plan(
    compound: str,
    profile: CompoundProfile,
    total_laps: int,
    fuel_capacity: float,
    pit_time_s: float,
    conditions: list[ConditionWindow] | None = None,
) -> RacePlan:
    """Build a plan using one compound, splitting into stints as needed."""
    fuel_stint = max(1, int(fuel_capacity / max(0.01, profile.fuel_per_lap)))
    effective_stint = min(fuel_stint, profile.estimated_life)

    stints: list[PlannedStint] = []
    lap = 1
    fuel = fuel_capacity

    while lap <= total_laps:
        laps_remaining = total_laps - lap + 1
        stint_len = min(effective_stint, laps_remaining)
        fuel_used = _fuel_for_laps(profile, stint_len)
        if fuel_used > fuel and stints:
            stint_len = max(1, int(fuel / max(0.01, profile.fuel_per_lap)))
            fuel_used = _fuel_for_laps(profile, stint_len)

        grip_end = max(0.0, 100.0 - profile.wear_per_lap * stint_len)
        fuel_to_add = 0.0 if not stints else min(
            fuel_capacity, _fuel_for_laps(profile, min(effective_stint, total_laps - lap + 1)) + profile.fuel_per_lap
        )

        stints.append(PlannedStint(
            compound=compound,
            start_lap=lap,
            end_lap=lap + stint_len - 1,
            fuel_at_start=fuel if not stints else fuel_to_add,
            fuel_to_add=fuel_to_add,
            grip_at_end=grip_end,
            estimated_time_s=stint_len * profile.avg_lap_time_s,
        ))

        lap += stint_len
        fuel = fuel_to_add - _fuel_for_laps(profile, stint_len) if fuel_to_add > 0 else fuel - fuel_used

    total_time = sum(s.estimated_time_s for s in stints) + max(0, len(stints) - 1) * pit_time_s
    fuel_finish = stints[-1].fuel_at_start - _fuel_for_laps(
        profile, stints[-1].end_lap - stints[-1].start_lap + 1
    ) if stints else 0.0

    return RacePlan(
        stints=stints,
        total_race_time_s=round(total_time, 1),
        fuel_at_finish=round(fuel_finish, 2),
    )


def optimize_strategy(
    total_laps: int,
    fuel_capacity: float,
    pit_time_s: float,
    profiles: dict[str, CompoundProfile],
    conditions: list[ConditionWindow] | None = None,
) -> RacePlan:
    """Find the fastest strategy across available compounds."""
    if not profiles or total_laps <= 0:
        return RacePlan(stints=[], total_race_time_s=0, fuel_at_finish=0)

    best: RacePlan | None = None

    # Try single-compound strategies
    for compound, profile in profiles.items():
        plan = _build_single_compound_plan(
            compound, profile, total_laps, fuel_capacity, pit_time_s, conditions,
        )
        if best is None or plan.total_race_time_s < best.total_race_time_s:
            best = plan

    # Try two-compound strategies (A then B)
    compounds = list(profiles.keys())
    for i, c1 in enumerate(compounds):
        for c2 in compounds:
            if c1 == c2:
                continue
            p1, p2 = profiles[c1], profiles[c2]
            split = min(p1.estimated_life, max(1, total_laps // 3))
            stint1_fuel = _fuel_for_laps(p1, split)
            if stint1_fuel > fuel_capacity:
                split = max(1, int(fuel_capacity / max(0.01, p1.fuel_per_lap)))
            remaining = total_laps - split
            if remaining <= 0:
                continue

            grip1 = max(0.0, 100.0 - p1.wear_per_lap * split)
            stint2_fuel_needed = _fuel_for_laps(p2, remaining)
            fuel_to_add = min(fuel_capacity, stint2_fuel_needed + p2.fuel_per_lap)
            grip2 = max(0.0, 100.0 - p2.wear_per_lap * remaining)

            stints = [
                PlannedStint(
                    compound=c1, start_lap=1, end_lap=split,
                    fuel_at_start=fuel_capacity, fuel_to_add=0.0,
                    grip_at_end=grip1,
                    estimated_time_s=split * p1.avg_lap_time_s,
                ),
                PlannedStint(
                    compound=c2, start_lap=split + 1, end_lap=total_laps,
                    fuel_at_start=fuel_to_add,
                    fuel_to_add=fuel_to_add,
                    grip_at_end=grip2,
                    estimated_time_s=remaining * p2.avg_lap_time_s,
                ),
            ]
            total_time = sum(s.estimated_time_s for s in stints) + pit_time_s
            fuel_finish = fuel_to_add - _fuel_for_laps(p2, remaining)

            plan = RacePlan(
                stints=stints,
                total_race_time_s=round(total_time, 1),
                fuel_at_finish=round(fuel_finish, 2),
            )
            if best is None or plan.total_race_time_s < best.total_race_time_s:
                best = plan

    return best or RacePlan(stints=[], total_race_time_s=0, fuel_at_finish=0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_race_strategy.py -v`
Expected: ALL PASS (existing tests + new ones)

- [ ] **Step 5: Write failing test — recalculate_live with RacePlan**

Add to `tests/test_race_strategy.py`:

```python
from lap_coach_logger.core.race_strategy import recalculate_live_plan


def test_recalculate_live_shifts_pit_window():
    soft = CompoundProfile(
        compound="soft", fuel_per_lap=2.5, fuel_curve=[2.5],
        wear_per_lap=3.0, estimated_life=20, avg_lap_time_s=90.0,
        lap_time_delta_s=0.0, avg_track_temp_c=30.0,
        total_laps_logged=30, stint_count=3, confidence="high",
    )
    original = optimize_strategy(
        total_laps=40, fuel_capacity=60.0, pit_time_s=25.0,
        profiles={"soft": soft},
    )
    original_pit = original.stints[0].end_lap

    # Actual fuel burn is higher than planned
    updated = recalculate_live_plan(
        plan=original,
        current_lap=5,
        current_fuel=45.0,
        actual_fuel_deltas=[3.2, 3.1, 3.0, 2.9, 2.8],
        actual_wear=15.0,
        profiles={"soft": soft},
        fuel_capacity=60.0,
        pit_time_s=25.0,
    )
    assert isinstance(updated, RacePlan)
    assert len(updated.stints) >= 1
```

- [ ] **Step 6: Implement recalculate_live_plan**

Add to `src/lap_coach_logger/core/race_strategy.py`:

```python
def recalculate_live_plan(
    plan: RacePlan,
    current_lap: int,
    current_fuel: float,
    actual_fuel_deltas: list[float],
    actual_wear: float,
    profiles: dict[str, CompoundProfile],
    fuel_capacity: float,
    pit_time_s: float,
    conditions: list[ConditionWindow] | None = None,
) -> RacePlan:
    """Recalculate strategy from current race position using actual data."""
    if not plan.stints:
        return plan

    total_laps = plan.stints[-1].end_lap
    remaining = total_laps - current_lap
    if remaining <= 0:
        return plan

    # Use actual fuel rate if we have data, otherwise profile rate
    actual_fuel_per_lap = (
        sum(actual_fuel_deltas) / len(actual_fuel_deltas)
        if actual_fuel_deltas else None
    )

    # Find which stint we're currently in
    current_compound = plan.stints[0].compound
    for stint in plan.stints:
        if stint.start_lap <= current_lap <= stint.end_lap:
            current_compound = stint.compound
            break

    if current_compound not in profiles:
        return plan

    profile = profiles[current_compound]
    effective_profile = CompoundProfile(
        compound=profile.compound,
        fuel_per_lap=actual_fuel_per_lap or profile.fuel_per_lap,
        fuel_curve=actual_fuel_deltas or profile.fuel_curve,
        wear_per_lap=profile.wear_per_lap,
        estimated_life=profile.estimated_life,
        avg_lap_time_s=profile.avg_lap_time_s,
        lap_time_delta_s=profile.lap_time_delta_s,
        avg_track_temp_c=profile.avg_track_temp_c,
        total_laps_logged=profile.total_laps_logged,
        stint_count=profile.stint_count,
        confidence=profile.confidence,
    )
    adjusted_profiles = dict(profiles)
    adjusted_profiles[current_compound] = effective_profile

    new_plan = optimize_strategy(
        total_laps=total_laps,
        fuel_capacity=fuel_capacity,
        pit_time_s=pit_time_s,
        profiles=adjusted_profiles,
        conditions=conditions,
    )

    # Generate divergence alerts
    alerts: list[StrategyAlert] = []
    if actual_fuel_per_lap and profile.fuel_per_lap > 0:
        fuel_diff = actual_fuel_per_lap - profile.fuel_per_lap
        if abs(fuel_diff) > 0.1:
            severity = "warning" if abs(fuel_diff) > 0.3 else "info"
            alerts.append(StrategyAlert(
                severity=severity,
                category="fuel",
                message=f"Fuel {fuel_diff:+.2f} L/lap vs plan",
                suggested_action="Pit window adjusted" if abs(fuel_diff) > 0.2 else None,
            ))

    new_plan.alerts.extend(alerts)
    return new_plan
```

- [ ] **Step 7: Run all strategy tests**

Run: `.venv/Scripts/python -m pytest tests/test_race_strategy.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/lap_coach_logger/core/race_strategy.py tests/test_race_strategy.py
git commit -m "feat: add RacePlan optimizer + live recalculation with divergence alerts"
```

---

## Task 3: Weather Monitor (iRacing)

**Files:**
- Create: `src/lap_coach_logger/core/strategy_weather.py`
- Test: `tests/test_strategy_weather.py`

- [ ] **Step 1: Write failing test — parse_forecast**

```python
# tests/test_strategy_weather.py
"""Tests for iRacing weather forecast parsing."""
from __future__ import annotations

from lap_coach_logger.core.strategy_weather import parse_forecast, ConditionWindow


def test_parse_dry_forecast():
    session_info = {
        "WeatherInfo": {
            "WeatherForecast": [
                {"time": 0, "temperature": 28.0, "precipitation": 0.0},
                {"time": 1800, "temperature": 27.0, "precipitation": 0.0},
            ]
        }
    }
    windows = parse_forecast(session_info, lap_time_s=90.0, total_laps=40)
    assert len(windows) >= 1
    assert all(w.track_state == "dry" for w in windows)
    assert all(w.precipitation == 0.0 for w in windows)


def test_parse_rain_forecast():
    session_info = {
        "WeatherInfo": {
            "WeatherForecast": [
                {"time": 0, "temperature": 24.0, "precipitation": 0.0},
                {"time": 900, "temperature": 22.0, "precipitation": 0.7},
                {"time": 1800, "temperature": 20.0, "precipitation": 0.3},
            ]
        }
    }
    windows = parse_forecast(session_info, lap_time_s=90.0, total_laps=40)
    assert len(windows) >= 2
    # First window should be dry
    assert windows[0].track_state == "dry"
    # A later window should be wet
    wet = [w for w in windows if w.track_state in ("wet", "damp")]
    assert len(wet) >= 1
    assert wet[0].recommended_compound in ("wet", "inter")


def test_parse_empty_forecast():
    windows = parse_forecast({}, lap_time_s=90.0, total_laps=40)
    assert windows == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_strategy_weather.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement strategy_weather.py**

```python
# src/lap_coach_logger/core/strategy_weather.py
"""iRacing weather forecast parsing and condition timeline.

Converts time-based WeatherForecast entries from the iRacing session
info into lap-based ConditionWindow objects for the strategy engine.
Non-iRacing sims skip this module entirely.
"""
from __future__ import annotations

import logging
from typing import Any

from lap_coach_logger.core.race_strategy import ConditionWindow

log = logging.getLogger(__name__)

_PRECIP_DAMP = 0.15
_PRECIP_WET = 0.4


def _classify_state(precipitation: float) -> str:
    if precipitation >= _PRECIP_WET:
        return "wet"
    if precipitation >= _PRECIP_DAMP:
        return "damp"
    return "dry"


def _recommend_compound(state: str) -> str:
    if state == "wet":
        return "wet"
    if state == "damp":
        return "inter"
    return "soft"


def parse_forecast(
    session_info: dict[str, Any],
    lap_time_s: float,
    total_laps: int,
) -> list[ConditionWindow]:
    """Convert iRacing WeatherForecast to lap-based condition windows."""
    weather = session_info.get("WeatherInfo", {})
    entries = weather.get("WeatherForecast", [])
    if not entries or lap_time_s <= 0 or total_laps <= 0:
        return []

    windows: list[ConditionWindow] = []
    race_duration_s = total_laps * lap_time_s

    for i, entry in enumerate(entries):
        time_s = float(entry.get("time", 0))
        temp = float(entry.get("temperature", 25.0))
        precip = float(entry.get("precipitation", 0.0))

        start_lap = max(1, int(time_s / lap_time_s) + 1)

        if i + 1 < len(entries):
            next_time = float(entries[i + 1].get("time", time_s))
            end_lap = min(total_laps, int(next_time / lap_time_s))
        else:
            end_lap = total_laps

        if start_lap > total_laps or end_lap < start_lap:
            continue

        state = _classify_state(precip)
        windows.append(ConditionWindow(
            start_lap=start_lap,
            end_lap=end_lap,
            track_temp_c=temp,
            precipitation=precip,
            track_state=state,
            recommended_compound=_recommend_compound(state),
        ))

    return windows


def update_from_live(
    current_windows: list[ConditionWindow],
    precipitation: float,
    track_wetness: float,
    track_temp: float,
    current_lap: int,
) -> list[ConditionWindow]:
    """Adjust forecast windows based on live telemetry readings."""
    if not current_windows:
        return current_windows

    actual_state = _classify_state(precipitation)
    updated: list[ConditionWindow] = []

    for w in current_windows:
        if w.end_lap < current_lap:
            updated.append(w)
            continue

        if w.start_lap <= current_lap <= w.end_lap:
            updated.append(ConditionWindow(
                start_lap=w.start_lap,
                end_lap=w.end_lap,
                track_temp_c=track_temp,
                precipitation=precipitation,
                track_state=actual_state,
                recommended_compound=_recommend_compound(actual_state),
            ))
        else:
            updated.append(w)

    return updated
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_strategy_weather.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/lap_coach_logger/core/strategy_weather.py tests/test_strategy_weather.py
git commit -m "feat: add iRacing weather forecast parser for strategy engine"
```

---

## Task 4: Stint Recorder

**Files:**
- Create: `src/lap_coach_logger/core/stint_recorder.py`
- Test: `tests/test_stint_recorder.py`

- [ ] **Step 1: Write failing test — recorder captures stint from samples**

```python
# tests/test_stint_recorder.py
"""Tests for live stint recording from telemetry stream."""
from __future__ import annotations

from pathlib import Path

from lap_coach_logger.core.stint_recorder import StintRecorder
from lap_coach_logger.core.stint_store import StintStore
from lap_coach_logger.core.schema import TelemetrySample


def _sample(lap: int, fuel: float, tyre_temp: float = 85.0, track_temp: float = 30.0) -> dict:
    return {
        "lap_number": lap,
        "fuel_level": fuel,
        "tyre_temp_lf": tyre_temp,
        "tyre_temp_rf": tyre_temp,
        "tyre_temp_lr": tyre_temp,
        "tyre_temp_rr": tyre_temp,
        "track_temp_c": track_temp,
        "air_temp_c": 22.0,
        "speed_kph": 200.0,
        "session_time_s": lap * 90.0,
    }


def test_recorder_captures_fuel_and_wear(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    recorder = StintRecorder(store=store, track="Monza", car="GT3")

    recorder.start("soft")
    # Simulate 3 laps: fuel drops 50→47→44→41
    for fuel in [50.0, 47.0, 44.0, 41.0]:
        lap = 4 - int((fuel - 41) / 3)
        recorder.push_snapshot(_sample(lap=lap, fuel=fuel))

    record = recorder.stop()
    assert record is not None
    assert record.compound == "soft"
    assert record.lap_count >= 2
    assert record.fuel_per_lap > 0
    assert len(record.fuel_per_lap_series) >= 1

    # Should be persisted
    stints = store.list_stints("Monza", "GT3")
    assert len(stints) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_stint_recorder.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement StintRecorder**

```python
# src/lap_coach_logger/core/stint_recorder.py
"""Live stint capture from telemetry stream.

Tracks per-lap fuel deltas and tire temperatures during a recording
session, then computes a StintRecord and writes it to the StintStore.
"""
from __future__ import annotations

import logging
from typing import Any

from lap_coach_logger.core.stint_store import StintRecord, StintStore

log = logging.getLogger(__name__)


class StintRecorder:
    """Captures fuel and tire data from live telemetry snapshots."""

    def __init__(self, store: StintStore, track: str, car: str) -> None:
        self._store = store
        self._track = track
        self._car = car
        self._compound: str = "unknown"
        self._recording = False
        self._last_lap: int = 0
        self._last_fuel: float | None = None
        self._fuel_deltas: list[float] = []
        self._lap_times: list[float] = []
        self._last_session_time: float | None = None
        self._temps_track: list[float] = []
        self._temps_air: list[float] = []
        self._tyre_temps_per_lap: list[tuple[float, float, float, float]] = []
        self._current_lap_tyre_temps: list[tuple[float, float, float, float]] = []
        self._source_session_id: str = ""
        self._source_label: str = ""

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self, compound: str, source_session_id: str = "", source_label: str = "") -> None:
        self._compound = compound
        self._recording = True
        self._last_lap = 0
        self._last_fuel = None
        self._fuel_deltas = []
        self._lap_times = []
        self._last_session_time = None
        self._temps_track = []
        self._temps_air = []
        self._tyre_temps_per_lap = []
        self._current_lap_tyre_temps = []
        self._source_session_id = source_session_id
        self._source_label = source_label
        log.info("Stint recording started: %s on %s / %s", compound, self._track, self._car)

    def push_snapshot(self, snap: dict[str, Any]) -> None:
        if not self._recording:
            return

        lap = snap.get("lap_number")
        fuel = snap.get("fuel_level")
        session_time = snap.get("session_time_s")
        track_temp = snap.get("track_temp_c")
        air_temp = snap.get("air_temp_c")

        if lap is None or fuel is None:
            return

        # Collect tyre temps
        tt = (
            snap.get("tyre_temp_lf") or 0.0,
            snap.get("tyre_temp_rf") or 0.0,
            snap.get("tyre_temp_lr") or 0.0,
            snap.get("tyre_temp_rr") or 0.0,
        )
        self._current_lap_tyre_temps.append(tt)

        # Detect lap change
        if lap != self._last_lap and self._last_lap > 0:
            if self._last_fuel is not None and fuel < self._last_fuel:
                self._fuel_deltas.append(round(self._last_fuel - fuel, 4))
            if self._last_session_time is not None and session_time is not None:
                lap_time = session_time - self._last_session_time
                if 20 < lap_time < 600:
                    self._lap_times.append(round(lap_time, 3))
            # Finalize lap tyre temps
            if self._current_lap_tyre_temps:
                n = len(self._current_lap_tyre_temps)
                avg = tuple(
                    sum(t[i] for t in self._current_lap_tyre_temps) / n
                    for i in range(4)
                )
                self._tyre_temps_per_lap.append(avg)
            self._current_lap_tyre_temps = []

        if track_temp is not None:
            self._temps_track.append(track_temp)
        if air_temp is not None:
            self._temps_air.append(air_temp)

        self._last_lap = lap
        self._last_fuel = fuel
        self._last_session_time = session_time

    def stop(self) -> StintRecord | None:
        if not self._recording:
            return None
        self._recording = False

        if not self._fuel_deltas:
            log.info("Stint recording stopped — no lap data captured")
            return None

        fuel_per_lap = sum(self._fuel_deltas) / len(self._fuel_deltas)
        avg_lap_time = (
            sum(self._lap_times) / len(self._lap_times) if self._lap_times else 0.0
        )
        avg_track_temp = (
            sum(self._temps_track) / len(self._temps_track) if self._temps_track else 0.0
        )
        avg_air_temp = (
            sum(self._temps_air) / len(self._temps_air) if self._temps_air else 0.0
        )

        # Estimate wear from tyre temp averages
        wear_per_lap = self._estimate_wear()
        grip_at_end = max(0.0, 100.0 - wear_per_lap * len(self._fuel_deltas))

        record = StintRecord(
            compound=self._compound,
            fuel_per_lap=round(fuel_per_lap, 3),
            fuel_per_lap_series=[round(d, 3) for d in self._fuel_deltas],
            wear_per_lap=round(wear_per_lap, 2),
            grip_at_end=round(grip_at_end, 1),
            lap_count=len(self._fuel_deltas),
            avg_lap_time_s=round(avg_lap_time, 3),
            track_temp_c=round(avg_track_temp, 1),
            air_temp_c=round(avg_air_temp, 1),
            source_session_id=self._source_session_id,
            source_label=self._source_label,
        )

        self._store.log_stint(self._track, self._car, record)
        log.info(
            "Stint recorded: %s %d laps, %.2f L/lap, %.1f%% wear/lap",
            self._compound, record.lap_count, record.fuel_per_lap, record.wear_per_lap,
        )
        return record

    def _estimate_wear(self) -> float:
        """Estimate grip wear per lap from tyre temperature data."""
        if not self._tyre_temps_per_lap:
            return 2.0  # default base wear

        optimal_low, optimal_high = 75.0, 100.0
        total_penalty = 0.0
        for temps in self._tyre_temps_per_lap:
            avg = sum(temps) / 4
            if avg < optimal_low:
                total_penalty += (optimal_low - avg) * 0.3
            elif avg > optimal_high:
                total_penalty += (avg - optimal_high) * 0.5
            total_penalty += 2.0  # base degradation

        return total_penalty / len(self._tyre_temps_per_lap)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_stint_recorder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lap_coach_logger/core/stint_recorder.py tests/test_stint_recorder.py
git commit -m "feat: add StintRecorder for live telemetry stint capture"
```

---

## Task 5: StrategyViewModel

**Files:**
- Create: `src/lap_coach_logger/viewmodels/strategy_vm.py`
- Test: `tests/test_strategy_vm.py`

- [ ] **Step 1: Write failing test — ViewModel exposes profiles and plan**

```python
# tests/test_strategy_vm.py
"""Tests for StrategyViewModel."""
from __future__ import annotations

from pathlib import Path

from tests.qt_mock import install
install()

from lap_coach_logger.core.stint_store import StintRecord, StintStore
from lap_coach_logger.viewmodels.strategy_vm import StrategyViewModel


def test_vm_loads_profiles_for_track_car(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    store.log_stint("Monza", "GT3", StintRecord(
        compound="soft", fuel_per_lap=2.8,
        fuel_per_lap_series=[2.9, 2.8, 2.7],
        wear_per_lap=3.0, grip_at_end=45.0, lap_count=3,
        avg_lap_time_s=90.0, track_temp_c=30.0, air_temp_c=22.0,
        source_session_id="s1", source_label="P1",
    ))
    vm = StrategyViewModel(store=store)
    vm.setTrackCar("Monza", "GT3")
    profiles = vm.compoundProfiles
    assert len(profiles) == 1
    assert profiles[0]["compound"] == "soft"
    assert profiles[0]["confidence"] == "low"


def test_vm_auto_optimize_produces_plan(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    store.log_stint("Monza", "GT3", StintRecord(
        compound="soft", fuel_per_lap=3.0,
        fuel_per_lap_series=[3.0], wear_per_lap=3.0, grip_at_end=40.0,
        lap_count=1, avg_lap_time_s=90.0, track_temp_c=30.0, air_temp_c=22.0,
        source_session_id="s1", source_label="P1",
    ))
    vm = StrategyViewModel(store=store)
    vm.setTrackCar("Monza", "GT3")
    vm.setTotalLaps(30)
    vm.setFuelCapacity(80.0)
    vm.setPitTime(25.0)
    vm.autoOptimize()
    plan = vm.racePlan
    assert len(plan) >= 1
    assert plan[0]["compound"] == "soft"


def test_vm_recording_toggle(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    vm = StrategyViewModel(store=store)
    vm.setTrackCar("Monza", "GT3")
    assert vm.isRecording is False
    vm.startRecording("soft")
    assert vm.isRecording is True
    vm.stopRecording()
    assert vm.isRecording is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_strategy_vm.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement StrategyViewModel**

```python
# src/lap_coach_logger/viewmodels/strategy_vm.py
"""StrategyViewModel — QObject bridge between strategy engine and QML."""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot

from lap_coach_logger.core.race_strategy import (
    ConditionWindow,
    RacePlan,
    optimize_strategy,
    recalculate_live_plan,
)
from lap_coach_logger.core.stint_recorder import StintRecorder
from lap_coach_logger.core.stint_store import CompoundProfile, StintStore

log = logging.getLogger(__name__)


class StrategyViewModel(QObject):

    profilesChanged = Signal()
    planChanged = Signal()
    stintLogChanged = Signal()
    alertsChanged = Signal()
    recordingChanged = Signal()
    weatherChanged = Signal()

    def __init__(self, store: StintStore, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._track = ""
        self._car = ""
        self._total_laps = 0
        self._fuel_capacity = 0.0
        self._pit_time = 25.0
        self._profiles: dict[str, CompoundProfile] = {}
        self._plan: RacePlan | None = None
        self._recorder: StintRecorder | None = None
        self._conditions: list[ConditionWindow] = []

    # ── Properties ──────────────────────────────────

    @Property(str, notify=profilesChanged)
    def trackName(self) -> str:
        return self._track

    @Property(str, notify=profilesChanged)
    def carName(self) -> str:
        return self._car

    @Property(int, notify=planChanged)
    def totalLaps(self) -> int:
        return self._total_laps

    @Property(float, notify=planChanged)
    def fuelCapacity(self) -> float:
        return self._fuel_capacity

    @Property(float, notify=planChanged)
    def pitTime(self) -> float:
        return self._pit_time

    @Property(list, notify=profilesChanged)
    def compoundProfiles(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self._profiles.values()]

    @Property(list, notify=planChanged)
    def racePlan(self) -> list[dict[str, Any]]:
        if self._plan is None:
            return []
        return [
            {
                "compound": s.compound,
                "start_lap": s.start_lap,
                "end_lap": s.end_lap,
                "fuel_at_start": round(s.fuel_at_start, 1),
                "fuel_to_add": round(s.fuel_to_add, 1),
                "grip_at_end": round(s.grip_at_end, 1),
                "estimated_time_s": round(s.estimated_time_s, 1),
            }
            for s in self._plan.stints
        ]

    @Property(list, notify=stintLogChanged)
    def stintLog(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._store.list_stints(self._track, self._car)]

    @Property(list, notify=alertsChanged)
    def alerts(self) -> list[dict[str, Any]]:
        if self._plan is None:
            return []
        return [
            {
                "severity": a.severity,
                "category": a.category,
                "message": a.message,
                "suggested_action": a.suggested_action,
            }
            for a in self._plan.alerts
        ]

    @Property(bool, notify=recordingChanged)
    def isRecording(self) -> bool:
        return self._recorder is not None and self._recorder.is_recording

    @Property(bool, notify=weatherChanged)
    def hasWeatherData(self) -> bool:
        return len(self._conditions) > 0

    @Property(list, notify=weatherChanged)
    def weatherTimeline(self) -> list[dict[str, Any]]:
        return [
            {
                "start_lap": w.start_lap,
                "end_lap": w.end_lap,
                "track_temp_c": w.track_temp_c,
                "precipitation": w.precipitation,
                "track_state": w.track_state,
                "recommended_compound": w.recommended_compound,
            }
            for w in self._conditions
        ]

    @Property(bool, notify=alertsChanged)
    def planDiverged(self) -> bool:
        if self._plan is None:
            return False
        return any(a.category == "divergence" for a in self._plan.alerts)

    @Property(float, notify=planChanged)
    def planFuelAtFinish(self) -> float:
        return self._plan.fuel_at_finish if self._plan else 0.0

    @Property(float, notify=planChanged)
    def planTotalTime(self) -> float:
        return self._plan.total_race_time_s if self._plan else 0.0

    @Property(int, notify=planChanged)
    def planNumStops(self) -> int:
        return self._plan.num_stops if self._plan else 0

    # ── Slots ───────────────────────────────────────

    @Slot(str, str)
    def setTrackCar(self, track: str, car: str) -> None:
        self._track = track
        self._car = car
        self._profiles = self._store.get_profiles(track, car)
        self.profilesChanged.emit()
        self.stintLogChanged.emit()

    @Slot(int)
    def setTotalLaps(self, n: int) -> None:
        self._total_laps = max(0, n)
        self.planChanged.emit()

    @Slot(float)
    def setFuelCapacity(self, v: float) -> None:
        self._fuel_capacity = max(0, v)
        self.planChanged.emit()

    @Slot(float)
    def setPitTime(self, v: float) -> None:
        self._pit_time = max(0, v)
        self.planChanged.emit()

    @Slot()
    def autoOptimize(self) -> None:
        if not self._profiles or self._total_laps <= 0:
            return
        self._plan = optimize_strategy(
            total_laps=self._total_laps,
            fuel_capacity=self._fuel_capacity,
            pit_time_s=self._pit_time,
            profiles=self._profiles,
            conditions=self._conditions or None,
        )
        self.planChanged.emit()
        self.alertsChanged.emit()

    @Slot(str)
    def startRecording(self, compound: str) -> None:
        self._recorder = StintRecorder(
            store=self._store, track=self._track, car=self._car,
        )
        self._recorder.start(compound)
        self.recordingChanged.emit()

    @Slot()
    def stopRecording(self) -> None:
        if self._recorder and self._recorder.is_recording:
            self._recorder.stop()
            self._profiles = self._store.get_profiles(self._track, self._car)
            self.profilesChanged.emit()
            self.stintLogChanged.emit()
        self.recordingChanged.emit()

    @Slot(str)
    def excludeLoggedStint(self, stint_id: str) -> None:
        self._store.exclude_stint(stint_id)
        self._profiles = self._store.get_profiles(self._track, self._car)
        self.profilesChanged.emit()
        self.stintLogChanged.emit()

    @Slot(str)
    def includeLoggedStint(self, stint_id: str) -> None:
        self._store.include_stint(stint_id)
        self._profiles = self._store.get_profiles(self._track, self._car)
        self.profilesChanged.emit()
        self.stintLogChanged.emit()

    @Slot()
    def clearStints(self) -> None:
        self._store.clear(self._track, self._car)
        self._profiles = {}
        self.profilesChanged.emit()
        self.stintLogChanged.emit()

    @Slot(int, int)
    def editStintLaps(self, index: int, laps: int) -> None:
        if self._plan is None or index < 0 or index >= len(self._plan.stints):
            return
        stint = self._plan.stints[index]
        new_end = stint.start_lap + laps - 1
        self._plan.stints[index] = PlannedStint(
            compound=stint.compound,
            start_lap=stint.start_lap,
            end_lap=new_end,
            fuel_at_start=stint.fuel_at_start,
            fuel_to_add=stint.fuel_to_add,
            grip_at_end=stint.grip_at_end,
            estimated_time_s=stint.estimated_time_s,
        )
        self.planChanged.emit()

    @Slot(str)
    def addStint(self, compound: str) -> None:
        if self._plan is None:
            return
        last_lap = self._plan.stints[-1].end_lap if self._plan.stints else 0
        if compound in self._profiles:
            profile = self._profiles[compound]
            stint_len = min(profile.estimated_life, max(1, self._total_laps - last_lap))
        else:
            stint_len = 10
        from lap_coach_logger.core.race_strategy import PlannedStint
        self._plan.stints.append(PlannedStint(
            compound=compound,
            start_lap=last_lap + 1,
            end_lap=last_lap + stint_len,
            fuel_at_start=self._fuel_capacity,
            fuel_to_add=self._fuel_capacity,
            grip_at_end=50.0,
            estimated_time_s=0.0,
        ))
        self.planChanged.emit()

    @Slot(int)
    def removeStint(self, index: int) -> None:
        if self._plan is None or index < 0 or index >= len(self._plan.stints):
            return
        self._plan.stints.pop(index)
        self.planChanged.emit()

    # ── Weather ─────────────────────────────────────

    def set_weather_conditions(self, conditions: list[ConditionWindow]) -> None:
        self._conditions = conditions
        self.weatherChanged.emit()

    # ── Live update ─────────────────────────────────

    def update_live(self, snap: dict[str, Any]) -> None:
        if self._recorder and self._recorder.is_recording:
            self._recorder.push_snapshot(snap)
```

Note: Add the missing import at the top of `editStintLaps`:

```python
from lap_coach_logger.core.race_strategy import PlannedStint
```

This import is already available at module level since we import from `race_strategy` in the header.

- [ ] **Step 4: Fix the PlannedStint import in editStintLaps**

The `PlannedStint` import needs to be at the module level. Add it to the existing import block:

```python
from lap_coach_logger.core.race_strategy import (
    ConditionWindow,
    PlannedStint,
    RacePlan,
    optimize_strategy,
    recalculate_live_plan,
)
```

And remove the local import from `addStint`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_strategy_vm.py -v`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add src/lap_coach_logger/viewmodels/strategy_vm.py tests/test_strategy_vm.py
git commit -m "feat: add StrategyViewModel bridging engine to QML"
```

---

## Task 6: QML Strategy Page + Nav Integration

**Files:**
- Create: `src/lap_coach_logger/qml/Pages/StrategyPage.qml`
- Modify: `src/lap_coach_logger/qml/AppShell.qml` (lines 15-20, 84-87)
- Modify: `src/lap_coach_logger/qml/Components/NavBar.qml` (lines 84-87)

- [ ] **Step 1: Create StrategyPage.qml**

Create `src/lap_coach_logger/qml/Pages/StrategyPage.qml` with the top-down layout from the spec. Key sections: header, compound profiles, race plan timeline, weather card, stint log table.

The QML file should follow the same patterns as `DashboardPage.qml`: `ScrollView` → background gradient `Rectangle` → `Column` with sections. Use `Theme.Tokens` for all colors, `Theme.Typography` for all fonts. Use the GlassSurface-style card pattern (dark rect with subtle border and refraction highlight).

- [ ] **Step 2: Add Strategy to NavBar**

Edit `src/lap_coach_logger/qml/Components/NavBar.qml` line 84-87, add strategy between live and history:

```qml
{ pageId: "dashboard", label: "Dashboard" },
{ pageId: "live",      label: "Live" },
{ pageId: "strategy",  label: "Strategy" },
{ pageId: "history",   label: "History" },
{ pageId: "overlays",  label: "Overlays" }
```

- [ ] **Step 3: Add Strategy to AppShell page map**

Edit `src/lap_coach_logger/qml/AppShell.qml` line 15-20, add strategy component:

```qml
readonly property var pageComponents: ({
    "dashboard": dashboardComponent,
    "live": liveComponent,
    "strategy": strategyComponent,
    "history": historyComponent,
    "overlays": overlaysComponent
})
```

And add the `Component` declaration near the other page components:

```qml
Component {
    id: strategyComponent
    Pages.StrategyPage {}
}
```

- [ ] **Step 4: Register StrategyViewModel in qml_bootstrap.py**

Edit `src/lap_coach_logger/qml_bootstrap.py` — in `build_view_models()`, create the StrategyViewModel and add it to the returned dict. In `run_qml_shell()`, register it as a context property:

Add to imports:
```python
from lap_coach_logger.viewmodels.strategy_vm import StrategyViewModel
from lap_coach_logger.core.stint_store import StintStore
from lap_coach_logger.utils.paths import runtime_dir
```

In `build_view_models()`:
```python
stint_store = StintStore(runtime_dir() / "stint_profiles.json")
strategy_vm = StrategyViewModel(store=stint_store)
```

Add `"strategy": strategy_vm` to the returned dict.

In `run_qml_shell()`, the existing loop registers all VMs as `{name}VM`, so `strategyVM` will be available in QML automatically.

- [ ] **Step 5: Initialize StintStore in bootstrap.py**

No change needed — the store is created inside `qml_bootstrap.py` when building view models.

- [ ] **Step 6: Verify the app launches with Strategy page**

Run: `.venv/Scripts/python -m lap_coach_logger`

Click "Strategy" in the nav bar. Verify the page loads without errors.

- [ ] **Step 7: Commit**

```bash
git add src/lap_coach_logger/qml/Pages/StrategyPage.qml
git add src/lap_coach_logger/qml/AppShell.qml
git add src/lap_coach_logger/qml/Components/NavBar.qml
git add src/lap_coach_logger/qml_bootstrap.py
git commit -m "feat: add Strategy page to nav + wire StrategyViewModel"
```

---

## Task 7: Overlay Widget Integration

**Files:**
- Modify: `src/lap_coach_logger/qml/Overlay/widgets/RaceStrategyWidget.qml`
- Modify: `src/lap_coach_logger/viewmodels/overlay_vm.py`

- [ ] **Step 1: Wire StrategyViewModel data into OverlayViewModel**

Edit `src/lap_coach_logger/viewmodels/overlay_vm.py` — add a method that accepts the strategy VM and reads plan data from it to feed the existing overlay properties (`strategyNextPitLap`, `strategyFuelToAdd`, etc.).

Add a `set_strategy_vm(vm)` method and connect signals.

- [ ] **Step 2: Add weather alert badge to RaceStrategyWidget.qml**

Edit `src/lap_coach_logger/qml/Overlay/widgets/RaceStrategyWidget.qml` — add a weather alert text row below the data rows that shows when `overlayVM.strategyWeatherAlert` is non-empty:

```qml
// Weather alert badge
Text {
    visible: root.weatherAlert !== ""
    text: root.weatherAlert
    font.family: Theme.Typography.monoFamily
    font.pixelSize: Math.round(9 * root.fontScale)
    font.weight: Font.Bold
    color: Theme.Tokens.racingPurple
    Layout.fillWidth: true
    Layout.topMargin: 4
}
```

Add `property string weatherAlert: ""` to the widget's public API.

- [ ] **Step 3: Verify overlay shows strategy data**

Run the app, enable the Race Strategy overlay widget, verify it displays plan data from the StrategyViewModel.

- [ ] **Step 4: Commit**

```bash
git add src/lap_coach_logger/viewmodels/overlay_vm.py
git add src/lap_coach_logger/qml/Overlay/widgets/RaceStrategyWidget.qml
git commit -m "feat: wire strategy engine into overlay widgets with weather alerts"
```

---

## Task 8: Session Import

**Files:**
- Modify: `src/lap_coach_logger/core/stint_store.py`
- Test: `tests/test_stint_store.py`

- [ ] **Step 1: Write failing test — import_from_session**

Add to `tests/test_stint_store.py`:

```python
def test_import_from_session(tmp_path: Path, bundled_session: Path):
    store = StintStore(tmp_path / "stints.json")
    record = store.import_from_session(bundled_session, compound="soft")
    assert record is not None
    assert record.compound == "soft"
    assert record.lap_count > 0
    assert record.fuel_per_lap > 0
    # Should be persisted
    stints = store.list_stints(record.source_label.split("/")[0] if "/" in record.source_label else "unknown", "unknown")
    # The import reads track/car from session.json
```

- [ ] **Step 2: Implement import_from_session on StintStore**

Add method to `StintStore` that reads `session.json`, `laps.json`, and the telemetry parquet file to extract fuel deltas and tire wear data. Use `pyarrow.parquet` for parquet reads.

- [ ] **Step 3: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_stint_store.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add src/lap_coach_logger/core/stint_store.py tests/test_stint_store.py
git commit -m "feat: add session import to StintStore"
```

---

## Task 9: Final Integration + Full Test Suite

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `.venv/Scripts/python -m pytest tests/ -q --tb=short --ignore=tests/test_desktop_workspaces.py --ignore=tests/test_ghost_widget.py --ignore=tests/test_overlay_browser_frontend.py --ignore=tests/test_overlay_window_manager.py`
Expected: ALL PASS

- [ ] **Step 2: Run Qt widget tests separately**

Run: `.venv/Scripts/python -m pytest tests/test_desktop_workspaces.py tests/test_ghost_widget.py tests/test_overlay_browser_frontend.py tests/test_overlay_window_manager.py -q`
Expected: ALL PASS

- [ ] **Step 3: Launch app and verify end-to-end**

Run: `.venv/Scripts/python -m lap_coach_logger`

Verify:
1. Strategy page appears in nav bar
2. Page loads with empty state ("no compounds logged")
3. Import stint works with a saved session
4. Record stint starts/stops and populates profiles
5. Auto-optimize produces a race plan
6. Race strategy overlay widget shows plan data

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: race strategy window with stint profiles, weather, and live recalc"
```
