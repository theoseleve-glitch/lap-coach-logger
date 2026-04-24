"""Tests for the enhanced session coordinator lifecycle.

Covers: minimum-save filtering, data-freeze detection, formal transition
transitions, and the coordinator's response to sim-found / sim-lost.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lap_coach_logger.config.models import AppConfig, SessionConfig
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.session_coordinator import SessionCoordinator
from lap_coach_logger.core.session_state import SessionState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(tmp_path: Path, **session_overrides) -> AppConfig:
    """Build an AppConfig pointing output at *tmp_path*."""
    scfg = SessionConfig(**session_overrides)
    return AppConfig(output_dir=str(tmp_path), session=scfg)


def _sample(
    *,
    raw_ts: float = 1.0,
    speed: float = 100.0,
    sim: str = "test_sim",
    session_uid: str = "uid-1",
    lap: int = 1,
) -> TelemetrySample:
    return TelemetrySample(
        sim=sim,
        session_uid=session_uid,
        speed_kph=speed,
        raw_source_timestamp=raw_ts,
        track_name="TestTrack",
        car_name="TestCar",
        session_type="Race",
        lap_number=lap,
    )


def _mock_adapter(active: bool = True) -> MagicMock:
    adapter = MagicMock()
    adapter.sim_name = "TestSim"
    adapter.connected = True
    adapter.connect.return_value = True
    adapter.is_session_active.return_value = active
    adapter.read_sample.return_value = _sample()
    return adapter


# ---------------------------------------------------------------------------
# Tests: State transitions on sim-found / sim-lost
# ---------------------------------------------------------------------------

class TestSimFoundLost:

    def test_on_sim_found_transitions_to_waiting(self, tmp_path: Path) -> None:
        coord = SessionCoordinator(_config(tmp_path))
        adapter = _mock_adapter(active=False)

        # Patch _start_monitor_loop so we don't spin up a real thread
        with patch.object(coord, "_start_monitor_loop"):
            coord.on_sim_found(adapter, True)

        assert coord.state == SessionState.WAITING_FOR_VALID_SESSION
        adapter.connect.assert_called_once()

    def test_on_sim_found_failed_connect_resets(self, tmp_path: Path) -> None:
        coord = SessionCoordinator(_config(tmp_path))
        adapter = _mock_adapter()
        adapter.connect.return_value = False

        accepted = coord.on_sim_found(adapter, True)
        assert accepted is False
        assert coord.state == SessionState.IDLE

    def test_on_sim_lost_during_waiting_resets(self, tmp_path: Path) -> None:
        coord = SessionCoordinator(_config(tmp_path))
        adapter = _mock_adapter()
        with patch.object(coord, "_start_monitor_loop"):
            coord.on_sim_found(adapter, True)
        assert coord.state == SessionState.WAITING_FOR_VALID_SESSION

        coord.on_sim_lost(adapter, False)
        assert coord.state == SessionState.IDLE


# ---------------------------------------------------------------------------
# Tests: Minimum-save filter
# ---------------------------------------------------------------------------

class TestMinSaveFilter:

    def test_short_session_discarded(self, tmp_path: Path) -> None:
        """Sessions with too few samples or too short duration are not saved."""
        coord = SessionCoordinator(_config(
            tmp_path,
            min_samples_to_save=10,
            min_duration_s=5.0,
        ))
        # Manually set up state as if we recorded a tiny session
        coord._fsm.transition(SessionState.SIMULATOR_DETECTED)
        coord._fsm.transition(SessionState.WAITING_FOR_VALID_SESSION)
        coord._fsm.transition(SessionState.ARMING)
        coord._fsm.transition(SessionState.RECORDING)
        coord._session_started_at = datetime.now(timezone.utc)
        coord._buffer = [_sample() for _ in range(3)]  # < 10

        coord._end_recording()

        # Should have discarded (no folder created)
        sessions = [p for p in tmp_path.iterdir() if not p.name.startswith("_tmp_")]
        assert len(sessions) == 0

    def test_long_session_saved(self, tmp_path: Path) -> None:
        """Sessions meeting thresholds are saved."""
        coord = SessionCoordinator(_config(
            tmp_path,
            min_samples_to_save=5,
            min_duration_s=0.0,
        ))
        coord._fsm.transition(SessionState.SIMULATOR_DETECTED)
        coord._fsm.transition(SessionState.WAITING_FOR_VALID_SESSION)
        coord._fsm.transition(SessionState.ARMING)
        coord._fsm.transition(SessionState.RECORDING)
        coord._session_started_at = datetime.now(timezone.utc)
        coord._buffer = [_sample(raw_ts=float(i)) for i in range(10)]

        coord._end_recording()

        sessions = [p for p in tmp_path.iterdir() if not p.name.startswith("_tmp_")]
        assert len(sessions) == 1


# ---------------------------------------------------------------------------
# Tests: Data-freeze detection
# ---------------------------------------------------------------------------

class TestDataFreeze:

    def test_no_freeze_when_timestamps_change(self, tmp_path: Path) -> None:
        coord = SessionCoordinator(_config(tmp_path, data_freeze_timeout_s=1.0))
        s1 = _sample(raw_ts=1.0)
        s2 = _sample(raw_ts=2.0)
        assert coord._is_data_frozen(s1, 1.0) is False
        assert coord._is_data_frozen(s2, 1.0) is False

    def test_freeze_when_timestamps_stuck(self, tmp_path: Path) -> None:
        coord = SessionCoordinator(_config(tmp_path, data_freeze_timeout_s=0.05))
        s = _sample(raw_ts=1.0)
        coord._is_data_frozen(s, 0.05)  # initialise
        time.sleep(0.06)
        assert coord._is_data_frozen(s, 0.05) is True

    def test_no_freeze_without_raw_ts(self, tmp_path: Path) -> None:
        """If raw_source_timestamp is None, freeze detection is skipped."""
        coord = SessionCoordinator(_config(tmp_path))
        s = _sample()
        s.raw_source_timestamp = None
        assert coord._is_data_frozen(s, 1.0) is False


# ---------------------------------------------------------------------------
# Tests: New state machine transitions
# ---------------------------------------------------------------------------

class TestNewStateTransitions:

    def test_waiting_to_arming_to_recording(self) -> None:
        from lap_coach_logger.core.session_state import SessionStateMachine
        fsm = SessionStateMachine()
        fsm.transition(SessionState.SIMULATOR_DETECTED)
        fsm.transition(SessionState.WAITING_FOR_VALID_SESSION)
        assert fsm.transition(SessionState.ARMING) is True
        assert fsm.transition(SessionState.RECORDING) is True

    def test_finalizing_to_ready_for_review(self) -> None:
        from lap_coach_logger.core.session_state import SessionStateMachine
        fsm = SessionStateMachine()
        fsm.transition(SessionState.SIMULATOR_DETECTED)
        fsm.transition(SessionState.WAITING_FOR_VALID_SESSION)
        fsm.transition(SessionState.ARMING)
        fsm.transition(SessionState.RECORDING)
        fsm.transition(SessionState.FINALIZING)
        assert fsm.transition(SessionState.READY_FOR_REVIEW) is True

    def test_ready_for_review_to_waiting(self) -> None:
        from lap_coach_logger.core.session_state import SessionStateMachine
        fsm = SessionStateMachine()
        fsm.transition(SessionState.SIMULATOR_DETECTED)
        fsm.transition(SessionState.WAITING_FOR_VALID_SESSION)
        fsm.transition(SessionState.ARMING)
        fsm.transition(SessionState.RECORDING)
        fsm.transition(SessionState.FINALIZING)
        fsm.transition(SessionState.READY_FOR_REVIEW)
        assert fsm.transition(SessionState.WAITING_FOR_VALID_SESSION) is True

    def test_detected_to_recording_invalid(self) -> None:
        """Direct simulator_detected → recording must be rejected."""
        from lap_coach_logger.core.session_state import SessionStateMachine
        fsm = SessionStateMachine()
        fsm.transition(SessionState.SIMULATOR_DETECTED)
        assert fsm.transition(SessionState.RECORDING) is False


# ---------------------------------------------------------------------------
# Tests: WAITING debounce for transient activity blips
# ---------------------------------------------------------------------------

class TestWaitingDebounce:

    def test_requires_two_consecutive_active_polls(self, tmp_path: Path) -> None:
        coord = SessionCoordinator(_config(tmp_path))
        assert coord._waiting_activity_confirmed(True) is False
        assert coord._waiting_activity_confirmed(True) is True

    def test_inactive_poll_resets_confirmation(self, tmp_path: Path) -> None:
        coord = SessionCoordinator(_config(tmp_path))
        assert coord._waiting_activity_confirmed(True) is False
        assert coord._waiting_activity_confirmed(False) is False
        assert coord._waiting_activity_confirmed(True) is False
        assert coord._waiting_activity_confirmed(True) is True


# ---------------------------------------------------------------------------
# Tests: Lap timing computation
# ---------------------------------------------------------------------------

class TestLapTiming:

    def test_lap_times_in_metadata(self, tmp_path: Path) -> None:
        """Verify per-lap times and best-lap are written to metadata."""
        import json

        coord = SessionCoordinator(_config(
            tmp_path,
            min_samples_to_save=5,
            min_duration_s=0.0,
        ))
        coord._fsm.transition(SessionState.SIMULATOR_DETECTED)
        coord._fsm.transition(SessionState.WAITING_FOR_VALID_SESSION)
        coord._fsm.transition(SessionState.ARMING)
        coord._fsm.transition(SessionState.RECORDING)
        coord._session_started_at = datetime.now(timezone.utc)

        # Laps are timed from the first observed sample in each segment to the last observed sample.
        # With one-second samples, the completed durations below are therefore 29s and 24s.
        buffer: list[TelemetrySample] = []
        for i in range(30):
            buffer.append(_sample(raw_ts=float(i), lap=1))
            buffer[-1].session_time_s = float(i)
        for i in range(30, 55):
            buffer.append(_sample(raw_ts=float(i), lap=2))
            buffer[-1].session_time_s = float(i)
        # Partial lap 3 still counts toward total classified laps, but has no completed timing entry.
        for i in range(55, 60):
            buffer.append(_sample(raw_ts=float(i), lap=3))
            buffer[-1].session_time_s = float(i)

        coord._buffer = buffer
        coord._end_recording()

        sessions = [p for p in tmp_path.iterdir() if not p.name.startswith("_tmp_")]
        assert len(sessions) == 1

        manifest = json.loads((sessions[0] / "session.json").read_text())
        # v2: lap count is in the session block
        assert manifest["session"]["lap_count"] == 3
        # Lap timing details are in laps.json
        laps = json.loads((sessions[0] / "laps.json").read_text())
        assert len(laps) == 3


class TestLiveDashboardSnapshot:

    def test_latest_snapshot_includes_dashboard_and_derived_metrics(self, tmp_path: Path) -> None:
        coord = SessionCoordinator(_config(tmp_path))

        first = _sample(raw_ts=1.0, lap=1)
        first.session_time_s = 30.0
        first.fuel_level = 50.0
        coord._append_sample(
            first,
            {
                "lap_time_s": 30.0,
                "fuel_level": 50.0,
                "current_sector_index": 2,
                "last_sector_time_s": 12.4,
                "session_status": "live",
                "flag_state": "green",
            },
        )

        second = _sample(raw_ts=2.0, lap=2)
        second.session_time_s = 121.0
        second.fuel_level = 46.0
        coord._append_sample(
            second,
            {
                "lap_time_s": 1.0,
                "last_lap_time_s": 91.0,
                "fuel_level": 46.0,
            },
        )

        snap = coord.latest_sample_snapshot()
        assert snap["lap_time_s"] == 1.0
        assert snap["last_lap_time_s"] == 91.0
        assert snap["best_lap_time_s"] == 91.0
        assert snap["fuel_per_lap_l"] == 4.0
        assert snap["laps_remaining_est"] == 11.5
        assert snap["sector_1_time_s"] == 12.4

    def test_live_coaching_snapshot_tracks_live_alerts(self, tmp_path: Path) -> None:
        coord = SessionCoordinator(_config(tmp_path))

        for index, session_time_s in enumerate((10.0, 10.4, 10.8)):
            sample = _sample(raw_ts=float(index + 1), lap=1)
            sample.lap_dist_pct = 0.10 + index * 0.01
            sample.session_time_s = session_time_s
            sample.speed_kph = 126.0
            sample.brake_pct = 0.95
            sample.long_accel_g = -1.28
            sample.tyre_temp_lf = 60.0
            sample.tyre_temp_rf = 61.0
            sample.tyre_temp_lr = 62.0
            sample.tyre_temp_rr = 60.0
            coord._append_sample(
                sample,
                {
                    "brake_temp_lf": 760.0,
                    "brake_temp_rf": 742.0,
                    "brake_temp_lr": 705.0,
                    "brake_temp_rr": 711.0,
                },
            )

        coach = coord.live_coaching_snapshot()
        titles = {item["title"] for item in coach["alerts"]}

        assert "Tyres cold" in titles
        assert "Excessive brake temp" in titles
        assert "Lockups detected" in titles

    def test_hardware_diagnostics_snapshot_tracks_input_quality(self, tmp_path: Path) -> None:
        coord = SessionCoordinator(_config(tmp_path))

        for index in range(14):
            sample = _sample(raw_ts=float(index + 1), lap=1)
            sample.session_time_s = index * 0.5
            sample.speed_kph = 130.0
            sample.throttle_pct = 0.15
            sample.brake_pct = 0.20
            sample.steering_deg = 14.0
            sample.lat_accel_g = 0.42
            sample.long_accel_g = -0.16
            coord._append_sample(sample, {"ffb_clip_pct": 0.99})

        diagnostics = coord.hardware_diagnostics_snapshot()
        rows = diagnostics["rows"]
        titles = {item["title"] for item in diagnostics["flags"]}

        assert rows["pedal_overlap"]["label"] == "High"
        assert rows["deadzone"]["label"] == "Possible Deadzone"
        assert rows["ffb_clipping"]["label"] == "Detected"
        assert "Pedal overlap" in titles
        assert "Deadzone suspected" in titles
        assert "FFB clipping" in titles

    def test_platform_analysis_snapshot_tracks_loaded_balance(self, tmp_path: Path) -> None:
        coord = SessionCoordinator(_config(tmp_path))

        for index in range(16):
            sample = _sample(raw_ts=float(index + 1), lap=1)
            sample.session_time_s = index * 0.5
            sample.speed_kph = 190.0
            sample.throttle_pct = 0.40
            sample.brake_pct = 0.08
            sample.steering_deg = 30.0
            sample.lat_accel_g = 0.40
            sample.long_accel_g = 0.10
            sample.pitch = 8.1
            sample.roll = 5.0
            coord._append_sample(
                sample,
                {
                    "ride_height_front": 62.0 if index < 6 else 48.0,
                    "ride_height_rear": 92.0 if index < 6 else 66.0,
                    "suspension_travel_lf": 8.0 if index < 6 else 15.0,
                    "suspension_travel_rf": 8.5 if index < 6 else 15.2,
                    "suspension_travel_lr": 6.0 if index < 6 else 10.0,
                    "suspension_travel_rr": 6.2 if index < 6 else 10.1,
                },
            )

        platform = coord.platform_analysis_snapshot()
        rows = platform["rows"]
        titles = {item["title"] for item in platform["flags"]}

        assert rows["ride_height_compression"]["label"] == "Bottoming Risk"
        assert rows["front_rear_limitation"]["label"] == "Front Limited"
        assert rows["aero_balance"]["label"] == "Front Aero Weak"
        assert "Bottoming risk" in titles
        assert "Aero balance suspicion" in titles


# ---------------------------------------------------------------------------
# Tests: Edge cases and recovery scenarios
# ---------------------------------------------------------------------------

class TestRecoveryScenarios:

    def test_duplicate_start_events_rejected(self, tmp_path: Path) -> None:
        coord = SessionCoordinator(_config(tmp_path))
        adapter = _mock_adapter(active=False)
        with patch.object(coord, "_start_monitor_loop"):
            accepted = coord.on_sim_found(adapter, True)
            second = coord.on_sim_found(adapter, True)
        assert accepted is True
        assert second is False

    def test_empty_session_transitions_through_failed_cleanup(self, tmp_path: Path) -> None:
        coord = SessionCoordinator(_config(
            tmp_path,
            min_samples_to_save=0,
            min_duration_s=0.0,
        ))
        coord._fsm.transition(SessionState.SIMULATOR_DETECTED)
        coord._fsm.transition(SessionState.WAITING_FOR_VALID_SESSION)
        coord._fsm.transition(SessionState.ARMING)
        coord._fsm.transition(SessionState.RECORDING)
        coord._session_started_at = datetime.now(timezone.utc)
        coord._buffer = []

        coord._end_recording()

        assert coord.state == SessionState.IDLE
        assert coord.health.snapshot().last_error is not None

    def test_stop_during_finalize_is_non_destructive(self, tmp_path: Path) -> None:
        coord = SessionCoordinator(_config(tmp_path))
        coord._fsm.transition(SessionState.SIMULATOR_DETECTED)
        coord._fsm.transition(SessionState.WAITING_FOR_VALID_SESSION)
        coord._fsm.transition(SessionState.ARMING)
        coord._fsm.transition(SessionState.RECORDING)
        coord._fsm.transition(SessionState.FINALIZING)

        coord.stop()

        assert coord.state == SessionState.FINALIZING
