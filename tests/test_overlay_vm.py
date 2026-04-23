"""Tests for OverlayViewModel -- live HUD overlay for QML."""

from __future__ import annotations

import pytest

from tests.qt_mock import install
install()

from lap_coach_logger.viewmodels.overlay_vm import OverlayViewModel  # noqa: E402


# ---------------------------------------------------------------------------
# Sample snapshots
# ---------------------------------------------------------------------------

SAMPLE_SNAPSHOT: dict = {
    "live": {
        "speed_kph": 245.7,
        "throttle_pct": 87.3,
        "brake_pct": 0.0,
        "current_lap": 5,
    },
    "track": "Spa-Francorchamps",
    "sim": "iRacing",
    "status": "Recording",
}

MINIMAL_SNAPSHOT: dict = {
    "sim": "ACC",
    "status": "Idle",
}


# ---------------------------------------------------------------------------
# Default property values
# ---------------------------------------------------------------------------

class TestDefaultProperties:
    """Before any snapshot arrives, properties should have safe defaults."""

    def test_speed_kph_default(self) -> None:
        vm = OverlayViewModel()
        assert vm.speedKph == 0.0

    def test_throttle_pct_default(self) -> None:
        vm = OverlayViewModel()
        assert vm.throttlePct == 0.0

    def test_brake_pct_default(self) -> None:
        vm = OverlayViewModel()
        assert vm.brakePct == 0.0

    def test_last_time_default(self) -> None:
        vm = OverlayViewModel()
        assert vm.lastTime == ""

    def test_best_time_default(self) -> None:
        vm = OverlayViewModel()
        assert vm.bestTime == ""

    def test_last_delta_default(self) -> None:
        vm = OverlayViewModel()
        assert vm.lastDelta == ""

    def test_sector_states_default(self) -> None:
        vm = OverlayViewModel()
        assert vm.sectorStates == []

    def test_lap_number_default(self) -> None:
        vm = OverlayViewModel()
        assert vm.lapNumber == 0

    def test_track_default(self) -> None:
        vm = OverlayViewModel()
        assert vm.track == ""

    def test_is_recording_default(self) -> None:
        vm = OverlayViewModel()
        assert vm.isRecording is False

    def test_elapsed_default(self) -> None:
        vm = OverlayViewModel()
        assert vm.elapsed == ""


# ---------------------------------------------------------------------------
# update_from_snapshot
# ---------------------------------------------------------------------------

class TestUpdateFromSnapshot:
    """update_from_snapshot should populate overlay properties from snap dict."""

    def test_speed_kph_populated(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot(SAMPLE_SNAPSHOT)
        assert vm.speedKph == 245.7

    def test_throttle_pct_populated(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot(SAMPLE_SNAPSHOT)
        assert vm.throttlePct == 87.3

    def test_brake_pct_populated(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot(SAMPLE_SNAPSHOT)
        assert vm.brakePct == 0.0

    def test_lap_number_populated(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot(SAMPLE_SNAPSHOT)
        assert vm.lapNumber == 5

    def test_track_populated_from_track(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot(SAMPLE_SNAPSHOT)
        assert vm.track == "Spa-Francorchamps"

    def test_track_falls_back_to_sim(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot({"sim": "ACC", "status": "Idle"})
        assert vm.track == "ACC"

    def test_is_recording_true(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot(SAMPLE_SNAPSHOT)
        assert vm.isRecording is True

    def test_is_recording_false_when_idle(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot(MINIMAL_SNAPSHOT)
        assert vm.isRecording is False

    def test_emits_inputs_changed(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot(SAMPLE_SNAPSHOT)
        assert vm.inputsChanged.call_count == 1

    def test_emits_context_changed(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot(SAMPLE_SNAPSHOT)
        assert vm.contextChanged.call_count == 1


# ---------------------------------------------------------------------------
# Missing live data defaults
# ---------------------------------------------------------------------------

class TestMissingLiveData:
    """When 'live' key is missing or empty, telemetry should default to zero."""

    def test_no_live_key_defaults_speed(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot(MINIMAL_SNAPSHOT)
        assert vm.speedKph == 0.0

    def test_no_live_key_defaults_throttle(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot(MINIMAL_SNAPSHOT)
        assert vm.throttlePct == 0.0

    def test_no_live_key_defaults_brake(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot(MINIMAL_SNAPSHOT)
        assert vm.brakePct == 0.0

    def test_no_live_key_defaults_lap_number(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot(MINIMAL_SNAPSHOT)
        assert vm.lapNumber == 0

    def test_empty_snapshot_defaults(self) -> None:
        vm = OverlayViewModel()
        vm.update_from_snapshot({})
        assert vm.speedKph == 0.0
        assert vm.track == ""
        assert vm.isRecording is False
