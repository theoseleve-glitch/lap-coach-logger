"""Tests for StrategyViewModel."""
from __future__ import annotations

from pathlib import Path

from tests.qt_mock import install
install()

from lap_coach_logger.core.stint_store import StintRecord, StintStore  # noqa: E402
from lap_coach_logger.viewmodels.strategy_vm import StrategyViewModel  # noqa: E402


def test_vm_loads_profiles_for_track_car(tmp_path: Path) -> None:
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


def test_vm_auto_optimize_produces_plan(tmp_path: Path) -> None:
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


def test_vm_recording_toggle(tmp_path: Path) -> None:
    store = StintStore(tmp_path / "stints.json")
    vm = StrategyViewModel(store=store)
    vm.setTrackCar("Monza", "GT3")
    assert vm.isRecording is False
    vm.startRecording("soft")
    assert vm.isRecording is True
    vm.stopRecording()
    assert vm.isRecording is False


def test_vm_race_mode_defaults_to_laps(tmp_path: Path) -> None:
    store = StintStore(tmp_path / "stints.json")
    vm = StrategyViewModel(store=store)
    assert vm.raceMode == "laps"
    assert vm.raceDurationHours == 0.0


def test_vm_set_race_mode_timed(tmp_path: Path) -> None:
    store = StintStore(tmp_path / "stints.json")
    vm = StrategyViewModel(store=store)
    vm.setRaceMode("timed")
    vm.setRaceDurationHours(1.5)
    assert vm.raceMode == "timed"
    assert vm.raceDurationHours == 1.5


def test_vm_model_availability_empty_when_no_profiles(tmp_path: Path) -> None:
    store = StintStore(tmp_path / "stints.json")
    vm = StrategyViewModel(store=store)
    vm.setTrackCar("Monza", "GT3")
    assert vm.modelAvailability == {}


def test_vm_autoOptimize_timed_race_produces_plan(tmp_path: Path) -> None:
    store = StintStore(tmp_path / "stints.json")
    store.log_stint("Monza", "GT3", StintRecord(
        compound="medium", fuel_per_lap=3.0,
        fuel_per_lap_series=[3.0], wear_per_lap=0.02, grip_at_end=60.0,
        lap_count=1, avg_lap_time_s=90.0, track_temp_c=30.0, air_temp_c=22.0,
        source_session_id="s1", source_label="P1",
    ))
    vm = StrategyViewModel(store=store)
    vm.setTrackCar("Monza", "GT3")
    vm.setFuelCapacity(100.0)
    vm.setPitTime(25.0)
    vm.setRaceMode("timed")
    vm.setRaceDurationHours(1.0)
    vm.autoOptimize()
    assert len(vm.racePlan) >= 1
