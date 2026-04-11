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
from lap_coach_logger.core.strategy_models import PitMeasurement, PitProfile


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


# ---------------------------------------------------------------------------
#  import_from_session
# ---------------------------------------------------------------------------

def test_import_from_session(tmp_path: Path, bundled_session: Path):
    """Import stint data from a saved session bundle."""
    store = StintStore(tmp_path / "stints.json")
    record = store.import_from_session(bundled_session, compound="soft")
    assert record is not None
    assert record.compound == "soft"
    assert record.lap_count >= 0
    assert record.source_session_id != ""


def test_import_from_session_missing_session_json(tmp_path: Path):
    """Return None when session.json does not exist."""
    empty_dir = tmp_path / "empty_session"
    empty_dir.mkdir()
    store = StintStore(tmp_path / "stints.json")
    result = store.import_from_session(empty_dir, compound="hard")
    assert result is None


def test_import_from_session_missing_telemetry(tmp_path: Path):
    """Return None when no telemetry file exists."""
    session_dir = tmp_path / "no_telemetry"
    session_dir.mkdir()
    (session_dir / "session.json").write_text(json.dumps({
        "track_name": "Monza",
        "car_name": "GT3",
        "session_type": "Race",
        "started_at_utc": "2026-01-01T00:00:00+00:00",
        "sample_count": 100,
        "session_id": "test-session",
    }))
    store = StintStore(tmp_path / "stints.json")
    result = store.import_from_session(session_dir, compound="medium")
    assert result is None


def test_import_from_session_persists_stint(tmp_path: Path, bundled_session: Path):
    """Imported stint is persisted and retrievable via list_stints."""
    store = StintStore(tmp_path / "stints.json")
    record = store.import_from_session(bundled_session, compound="medium")
    assert record is not None
    # Reload from disk
    store2 = StintStore(tmp_path / "stints.json")
    stints = store2.list_stints("Spa", "GT3")
    assert len(stints) == 1
    assert stints[0].id == record.id
    assert stints[0].compound == "medium"


def test_import_from_session_populates_per_lap_data(
    tmp_path: Path, bundled_session: Path,
):
    """import_from_session populates lap_times_s and lap_avg_temps_c."""
    store = StintStore(tmp_path / "stints.json")
    record = store.import_from_session(bundled_session, compound="soft")
    assert record is not None
    # Bundled session has 3 laps -> 3 entries each
    assert len(record.lap_times_s) == record.lap_count
    assert len(record.lap_avg_temps_c) == record.lap_count
    # Lap times derived from session_time_s should be positive
    for lap_time in record.lap_times_s:
        assert lap_time >= 0.0


# ---------------------------------------------------------------------------
#  Per-lap data roundtrip & fitted model integration (Task 2)
# ---------------------------------------------------------------------------

def _make_detailed_record(
    compound: str,
    lap_times: list[float],
    lap_temps: list[float],
    track_temp: float = 30.0,
) -> StintRecord:
    """Create a StintRecord with per-lap data filled in."""
    return StintRecord(
        compound=compound,
        fuel_per_lap=2.5,
        fuel_per_lap_series=[2.5] * len(lap_times),
        wear_per_lap=1.8,
        grip_at_end=60.0,
        lap_count=len(lap_times),
        avg_lap_time_s=sum(lap_times) / len(lap_times) if lap_times else 0.0,
        track_temp_c=track_temp,
        air_temp_c=22.0,
        source_session_id="sess",
        source_label="P",
        lap_times_s=list(lap_times),
        lap_avg_temps_c=list(lap_temps),
    )


def test_stint_record_serializes_per_lap_data():
    """StintRecord with lap_times_s and lap_avg_temps_c roundtrips through
    to_dict/from_dict."""
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
        lap_times_s=[91.5, 91.2, 90.9],
        lap_avg_temps_c=[82.0, 85.0, 88.0],
    )
    d = rec.to_dict()
    assert d["lap_times_s"] == [91.5, 91.2, 90.9]
    assert d["lap_avg_temps_c"] == [82.0, 85.0, 88.0]
    restored = StintRecord.from_dict(d)
    assert restored.lap_times_s == [91.5, 91.2, 90.9]
    assert restored.lap_avg_temps_c == [82.0, 85.0, 88.0]


def test_stint_record_from_dict_backward_compat_missing_per_lap():
    """Old stints without per-lap fields still load (default to []).
    """
    legacy_dict = {
        "id": "abc",
        "compound": "medium",
        "fuel_per_lap": 2.5,
        "fuel_per_lap_series": [],
        "wear_per_lap": 1.5,
        "grip_at_end": 70.0,
        "lap_count": 5,
        "avg_lap_time_s": 90.0,
        "track_temp_c": 30.0,
        "air_temp_c": 22.0,
        "source_session_id": "x",
        "source_label": "y",
        "recorded_at": "2026-01-01T00:00:00+00:00",
        "excluded": False,
        # lap_times_s and lap_avg_temps_c intentionally missing
    }
    rec = StintRecord.from_dict(legacy_dict)
    assert rec.lap_times_s == []
    assert rec.lap_avg_temps_c == []


def test_compound_profile_includes_fitted_models(tmp_path: Path):
    """After logging enough stints with per-lap data, the profile has
    thermal/warmup/degradation populated."""
    store = StintStore(tmp_path / "stints.json")
    # Log 3 stints with varying temps and warmup pattern
    for stint_idx in range(3):
        lap_times: list[float] = []
        lap_temps: list[float] = []
        for lap in range(12):
            # Warmup: first 3 laps slower, then settle
            if lap == 0:
                base_time = 92.5
                temp = 70.0 + stint_idx * 2
            elif lap == 1:
                base_time = 91.5
                temp = 75.0 + stint_idx * 2
            elif lap == 2:
                base_time = 90.8
                temp = 80.0 + stint_idx * 2
            else:
                # Steady state with mild degradation
                base_time = 90.0 + 0.02 * (lap - 3)
                temp = 85.0 + stint_idx * 2 + 0.3 * (lap - 3)
            lap_times.append(base_time)
            lap_temps.append(temp)
        rec = _make_detailed_record("soft", lap_times, lap_temps)
        store.log_stint("t", "c", rec)

    profiles = store.get_profiles("t", "c")
    p = profiles["soft"]
    # At minimum warmup should fit (3 stints), degradation needs >=10 laps per stint
    assert p.warmup is not None
    # Warmup is dict serialization
    assert "fitted" in p.warmup
    # Thermal + Degradation require enough samples/spread; with 36 laps they should fit
    assert p.thermal is not None
    assert "optimal_temp_low" in p.thermal
    assert p.degradation is not None
    assert "deg_rate_per_lap" in p.degradation


def test_profile_models_none_when_insufficient_data(tmp_path: Path):
    """A single short stint results in None models."""
    store = StintStore(tmp_path / "stints.json")
    # 3 laps only — below fit_thermal (5), fit_degradation (10), fit_warmup (3 stints)
    rec = _make_detailed_record(
        "hard",
        lap_times=[92.0, 91.5, 91.0],
        lap_temps=[75.0, 78.0, 80.0],
    )
    store.log_stint("t", "c", rec)
    profiles = store.get_profiles("t", "c")
    p = profiles["hard"]
    assert p.thermal is None
    assert p.warmup is None
    assert p.degradation is None


def test_compound_profile_models_serialize_in_to_dict(tmp_path: Path):
    """CompoundProfile.to_dict() includes thermal/warmup/degradation keys."""
    store = StintStore(tmp_path / "stints.json")
    rec = _make_detailed_record(
        "soft",
        lap_times=[91.0, 90.5, 90.3],
        lap_temps=[80.0, 82.0, 84.0],
    )
    store.log_stint("t", "c", rec)
    p = store.get_profiles("t", "c")["soft"]
    d = p.to_dict()
    assert "thermal" in d
    assert "warmup" in d
    assert "degradation" in d


def test_pit_profile_storage(tmp_path: Path):
    """log_pit_measurement persists, get_pit_profile returns fitted PitProfile."""
    path = tmp_path / "stints.json"
    store = StintStore(path)
    m1 = PitMeasurement(
        total_time_s=25.0,
        fuel_added=30.0,
        tires_changed=False,
        fuel_at_entry=10.0,
        fuel_at_exit=40.0,
        compound_before="soft",
        compound_after="soft",
        recorded_at=1000.0,
    )
    m2 = PitMeasurement(
        total_time_s=28.0,
        fuel_added=40.0,
        tires_changed=True,
        fuel_at_entry=5.0,
        fuel_at_exit=45.0,
        compound_before="soft",
        compound_after="medium",
        recorded_at=2000.0,
    )
    store.log_pit_measurement("monza", m1)
    store.log_pit_measurement("monza", m2)

    profile = store.get_pit_profile("monza")
    assert isinstance(profile, PitProfile)
    assert profile.track == "monza"
    assert len(profile.measurements) == 2
    # With two measurements the fit returns non-None betas
    assert profile.beta_transit is not None
    assert profile.beta_fuel_rate is not None

    # Persistence roundtrip
    store2 = StintStore(path)
    profile2 = store2.get_pit_profile("monza")
    assert len(profile2.measurements) == 2


def test_pit_profile_empty_track(tmp_path: Path):
    """Requesting a PitProfile for a track with no measurements returns
    PitProfile with None betas and no measurements."""
    store = StintStore(tmp_path / "stints.json")
    profile = store.get_pit_profile("unknown_track")
    assert isinstance(profile, PitProfile)
    assert profile.track == "unknown_track"
    assert profile.measurements == []
    assert profile.beta_transit is None


def test_pit_profiles_do_not_pollute_stint_listings(tmp_path: Path):
    """After logging pit measurements, list_stints and get_profiles must
    not treat the `_pit_profiles` meta-key as a track::car entry."""
    store = StintStore(tmp_path / "stints.json")
    store.log_pit_measurement("monza", PitMeasurement(
        total_time_s=25.0,
        fuel_added=30.0,
        tires_changed=False,
        fuel_at_entry=10.0,
        fuel_at_exit=40.0,
        compound_before="soft",
        compound_after="soft",
        recorded_at=1000.0,
    ))
    # Logging a real stint still works
    store.log_stint("t", "c", _make_record("soft", 2.5, 2.0, 5, 90.0))
    # list_stints of non-existent key should still be []
    assert store.list_stints("_pit_profiles", "") == []
    # The legitimate stint is still there
    assert len(store.list_stints("t", "c")) == 1
