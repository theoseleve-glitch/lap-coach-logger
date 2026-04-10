"""Tests for StintStore persistence and compound profile aggregation."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from lap_coach_logger.core.stint_store import (
    CompoundProfile,
    StintRecord,
    StintStore,
)


# ---------------------------------------------------------------------------
#  StintRecord roundtrip
# ---------------------------------------------------------------------------

def test_stint_record_defaults():
    rec = StintRecord(
        compound="soft",
        fuel_per_lap=2.5,
        fuel_per_lap_series=[2.6, 2.5, 2.4],
        wear_per_lap=1.8,
        grip_at_end=62.0,
        lap_count=3,
        avg_lap_time_s=91.2,
        track_temp_c=32.0,
        air_temp_c=24.0,
        source_session_id="sess-001",
        source_label="Practice 1",
    )
    assert isinstance(rec.id, str)
    assert len(rec.id) > 0
    assert rec.excluded is False
    assert rec.recorded_at  # non-empty ISO string


def test_stint_record_to_dict_from_dict_roundtrip():
    rec = StintRecord(
        compound="medium",
        fuel_per_lap=3.1,
        fuel_per_lap_series=[3.2, 3.1, 3.0],
        wear_per_lap=1.5,
        grip_at_end=70.0,
        lap_count=3,
        avg_lap_time_s=89.0,
        track_temp_c=30.0,
        air_temp_c=22.0,
        source_session_id="sess-002",
        source_label="Race",
    )
    d = rec.to_dict()
    restored = StintRecord.from_dict(d)
    assert restored.compound == rec.compound
    assert restored.fuel_per_lap == rec.fuel_per_lap
    assert restored.fuel_per_lap_series == rec.fuel_per_lap_series
    assert restored.wear_per_lap == rec.wear_per_lap
    assert restored.grip_at_end == rec.grip_at_end
    assert restored.lap_count == rec.lap_count
    assert restored.avg_lap_time_s == rec.avg_lap_time_s
    assert restored.track_temp_c == rec.track_temp_c
    assert restored.air_temp_c == rec.air_temp_c
    assert restored.source_session_id == rec.source_session_id
    assert restored.source_label == rec.source_label
    assert restored.id == rec.id
    assert restored.recorded_at == rec.recorded_at
    assert restored.excluded == rec.excluded


# ---------------------------------------------------------------------------
#  StintStore log + list + persist
# ---------------------------------------------------------------------------

def test_store_log_and_list(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    rec = StintRecord(
        compound="soft",
        fuel_per_lap=2.5,
        fuel_per_lap_series=[2.6, 2.5, 2.4],
        wear_per_lap=1.8,
        grip_at_end=62.0,
        lap_count=3,
        avg_lap_time_s=91.2,
        track_temp_c=32.0,
        air_temp_c=24.0,
        source_session_id="sess-001",
        source_label="P1",
    )
    store.log_stint("monza", "ferrari_488", rec)
    stints = store.list_stints("monza", "ferrari_488")
    assert len(stints) == 1
    assert stints[0].id == rec.id


def test_store_persists_to_disk(tmp_path: Path):
    path = tmp_path / "stints.json"
    store = StintStore(path)
    rec = StintRecord(
        compound="hard",
        fuel_per_lap=2.0,
        fuel_per_lap_series=[2.1, 2.0, 1.9],
        wear_per_lap=1.0,
        grip_at_end=80.0,
        lap_count=3,
        avg_lap_time_s=92.0,
        track_temp_c=28.0,
        air_temp_c=20.0,
        source_session_id="sess-003",
        source_label="Q",
    )
    store.log_stint("spa", "porsche_911", rec)

    # Re-open from same file
    store2 = StintStore(path)
    stints = store2.list_stints("spa", "porsche_911")
    assert len(stints) == 1
    assert stints[0].compound == "hard"


def test_store_separate_track_car_keys(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    rec_a = StintRecord(
        compound="soft", fuel_per_lap=2.5, fuel_per_lap_series=[],
        wear_per_lap=1.8, grip_at_end=60.0, lap_count=5,
        avg_lap_time_s=90.0, track_temp_c=30.0, air_temp_c=22.0,
        source_session_id="s1", source_label="P1",
    )
    rec_b = StintRecord(
        compound="medium", fuel_per_lap=2.2, fuel_per_lap_series=[],
        wear_per_lap=1.2, grip_at_end=75.0, lap_count=8,
        avg_lap_time_s=91.0, track_temp_c=31.0, air_temp_c=23.0,
        source_session_id="s2", source_label="P2",
    )
    store.log_stint("monza", "ferrari", rec_a)
    store.log_stint("spa", "porsche", rec_b)
    assert len(store.list_stints("monza", "ferrari")) == 1
    assert len(store.list_stints("spa", "porsche")) == 1
    assert len(store.list_stints("monza", "porsche")) == 0


# ---------------------------------------------------------------------------
#  CompoundProfile aggregation
# ---------------------------------------------------------------------------

def _make_record(
    compound: str, fuel: float, wear: float, laps: int,
    lap_time: float, series: list[float] | None = None,
    track_temp: float = 30.0,
) -> StintRecord:
    return StintRecord(
        compound=compound,
        fuel_per_lap=fuel,
        fuel_per_lap_series=series or [],
        wear_per_lap=wear,
        grip_at_end=60.0,
        lap_count=laps,
        avg_lap_time_s=lap_time,
        track_temp_c=track_temp,
        air_temp_c=22.0,
        source_session_id="s",
        source_label="P",
    )


def test_compound_profile_weighted_fuel(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    # Stint A: 5 laps @ 3.0 L/lap
    store.log_stint("t", "c", _make_record("soft", 3.0, 2.0, 5, 90.0))
    # Stint B: 15 laps @ 2.0 L/lap
    store.log_stint("t", "c", _make_record("soft", 2.0, 2.0, 15, 90.0))

    profiles = store.get_profiles("t", "c")
    p = profiles["soft"]
    # Weighted average: (3.0*5 + 2.0*15) / (5+15) = 45/20 = 2.25
    assert abs(p.fuel_per_lap - 2.25) < 0.01


def test_compound_profile_estimated_life(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    store.log_stint("t", "c", _make_record("medium", 2.5, 2.0, 10, 90.0))
    profiles = store.get_profiles("t", "c")
    p = profiles["medium"]
    # estimated_life = (100-40) / wear_per_lap = 60 / 2.0 = 30
    assert p.estimated_life == 30


def test_compound_profile_confidence_levels(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    # 5 laps -> "low"
    store.log_stint("t", "c", _make_record("soft", 2.5, 2.0, 5, 90.0))
    assert store.get_profiles("t", "c")["soft"].confidence == "low"

    # Add 15 more -> total 20 -> "medium"
    store.log_stint("t", "c", _make_record("soft", 2.5, 2.0, 15, 90.0))
    assert store.get_profiles("t", "c")["soft"].confidence == "medium"

    # Add 20 more -> total 40 -> "high"
    store.log_stint("t", "c", _make_record("soft", 2.5, 2.0, 20, 90.0))
    assert store.get_profiles("t", "c")["soft"].confidence == "high"


def test_compound_profile_fuel_curve_averaged(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    # Stint A: 3-lap fuel series [2.6, 2.5, 2.4]
    store.log_stint("t", "c", _make_record(
        "soft", 2.5, 2.0, 3, 90.0, series=[2.6, 2.5, 2.4],
    ))
    # Stint B: 3-lap fuel series [2.8, 2.7, 2.6]
    store.log_stint("t", "c", _make_record(
        "soft", 2.7, 2.0, 3, 90.0, series=[2.8, 2.7, 2.6],
    ))
    profiles = store.get_profiles("t", "c")
    curve = profiles["soft"].fuel_curve
    # Average: [(2.6+2.8)/2, (2.5+2.7)/2, (2.4+2.6)/2] = [2.7, 2.6, 2.5]
    assert len(curve) == 3
    assert abs(curve[0] - 2.7) < 0.01
    assert abs(curve[1] - 2.6) < 0.01
    assert abs(curve[2] - 2.5) < 0.01


def test_compound_profile_to_dict(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    store.log_stint("t", "c", _make_record("hard", 2.0, 1.0, 10, 92.0))
    profiles = store.get_profiles("t", "c")
    d = profiles["hard"].to_dict()
    assert d["compound"] == "hard"
    assert "fuel_per_lap" in d
    assert "confidence" in d
    assert "estimated_life" in d


# ---------------------------------------------------------------------------
#  Excluded stints not aggregated
# ---------------------------------------------------------------------------

def test_excluded_stints_not_in_profiles(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    rec_good = _make_record("soft", 2.5, 2.0, 10, 90.0)
    rec_bad = _make_record("soft", 5.0, 4.0, 10, 100.0)
    store.log_stint("t", "c", rec_good)
    store.log_stint("t", "c", rec_bad)

    # Before exclusion: aggregation includes both
    p_before = store.get_profiles("t", "c")["soft"]
    assert p_before.total_laps_logged == 20

    # Exclude the bad stint
    store.exclude_stint(rec_bad.id)
    p_after = store.get_profiles("t", "c")["soft"]
    assert p_after.total_laps_logged == 10
    assert abs(p_after.fuel_per_lap - 2.5) < 0.01


def test_include_stint_restores_aggregation(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    rec = _make_record("soft", 2.5, 2.0, 10, 90.0)
    store.log_stint("t", "c", rec)
    store.exclude_stint(rec.id)
    assert store.get_profiles("t", "c") == {}

    store.include_stint(rec.id)
    profiles = store.get_profiles("t", "c")
    assert "soft" in profiles
    assert profiles["soft"].total_laps_logged == 10


def test_clear_track_car(tmp_path: Path):
    store = StintStore(tmp_path / "stints.json")
    store.log_stint("t", "c", _make_record("soft", 2.5, 2.0, 5, 90.0))
    store.log_stint("t", "c2", _make_record("hard", 2.0, 1.0, 5, 91.0))
    store.clear("t", "c")
    assert len(store.list_stints("t", "c")) == 0
    assert len(store.list_stints("t", "c2")) == 1
