"""Tests for StintRecorder — live telemetry stint capture."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from lap_coach_logger.core.stint_recorder import StintRecorder
from lap_coach_logger.core.stint_store import StintStore
from lap_coach_logger.core.strategy_models import PitMeasurement


def _snap(
    lap: int,
    fuel: float,
    session_time: float,
    tyre_temp: float = 85.0,
    track_temp: float = 30.0,
    air_temp: float = 22.0,
    speed: float = 200.0,
) -> dict:
    """Build a minimal telemetry snapshot dict."""
    return {
        "lap_number": lap,
        "fuel_level": fuel,
        "tyre_temp_lf": tyre_temp,
        "tyre_temp_rf": tyre_temp,
        "tyre_temp_lr": tyre_temp,
        "tyre_temp_rr": tyre_temp,
        "track_temp_c": track_temp,
        "air_temp_c": air_temp,
        "speed_kph": speed,
        "session_time_s": session_time,
    }


class TestRecorderCapturesFuelAndWear:
    """Push snapshots across 3+ laps and verify recording results."""

    def test_recorder_captures_fuel_and_wear(self, tmp_path: Path) -> None:
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Monza", car="GT3")

        recorder.start("Soft", source_session_id="sess-1", source_label="Practice")

        # Lap 1 snapshots (fuel 50 -> ...)
        recorder.push_snapshot(_snap(lap=1, fuel=50.0, session_time=0.0))
        recorder.push_snapshot(_snap(lap=1, fuel=49.5, session_time=30.0))
        recorder.push_snapshot(_snap(lap=1, fuel=49.0, session_time=60.0))

        # Cross to lap 2 -- fuel delta = 50.0 - 48.0 = 2.0
        recorder.push_snapshot(_snap(lap=2, fuel=48.0, session_time=90.0))
        recorder.push_snapshot(_snap(lap=2, fuel=47.5, session_time=120.0))

        # Cross to lap 3 -- fuel delta = 48.0 - 46.0 = 2.0
        recorder.push_snapshot(_snap(lap=3, fuel=46.0, session_time=180.0))
        recorder.push_snapshot(_snap(lap=3, fuel=45.5, session_time=210.0))

        # Cross to lap 4 -- fuel delta = 46.0 - 44.5 = 1.5
        recorder.push_snapshot(_snap(lap=4, fuel=44.5, session_time=270.0))

        record = recorder.stop()

        assert record is not None
        assert record.lap_count == 3
        assert record.fuel_per_lap_series == [2.0, 2.0, 1.5]
        assert abs(record.fuel_per_lap - (2.0 + 2.0 + 1.5) / 3) < 1e-6
        assert record.compound == "Soft"
        assert record.source_session_id == "sess-1"
        assert record.source_label == "Practice"

        # Tyre temps = 85.0 (in optimal 75-100 range), so base wear = 2.0
        assert abs(record.wear_per_lap - 2.0) < 1e-6

        # Verify persisted to store
        persisted = store.list_stints("Monza", "GT3")
        assert len(persisted) == 1
        assert persisted[0].id == record.id

    def test_cold_tyre_penalty(self, tmp_path: Path) -> None:
        """Tyres below 75 C incur a cold-wear penalty."""
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Monza", car="GT3")
        recorder.start("Hard")

        # All temps at 55 C -> penalty = (75-55)*0.3 = 6.0, total = 8.0
        recorder.push_snapshot(_snap(lap=1, fuel=50.0, session_time=0.0, tyre_temp=55.0))
        recorder.push_snapshot(_snap(lap=2, fuel=48.0, session_time=90.0, tyre_temp=55.0))
        recorder.push_snapshot(_snap(lap=3, fuel=46.0, session_time=180.0, tyre_temp=55.0))

        record = recorder.stop()
        assert record is not None
        assert abs(record.wear_per_lap - 8.0) < 1e-6

    def test_hot_tyre_penalty(self, tmp_path: Path) -> None:
        """Tyres above 100 C incur a hot-wear penalty."""
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Monza", car="GT3")
        recorder.start("Soft")

        # All temps at 120 C -> penalty = (120-100)*0.5 = 10.0, total = 12.0
        recorder.push_snapshot(_snap(lap=1, fuel=50.0, session_time=0.0, tyre_temp=120.0))
        recorder.push_snapshot(_snap(lap=2, fuel=48.0, session_time=90.0, tyre_temp=120.0))
        recorder.push_snapshot(_snap(lap=3, fuel=46.0, session_time=180.0, tyre_temp=120.0))

        record = recorder.stop()
        assert record is not None
        assert abs(record.wear_per_lap - 12.0) < 1e-6


class TestRecorderReturnsNoneWhenNoLaps:
    """Start + stop immediately should produce None."""

    def test_recorder_returns_none_when_no_laps(self, tmp_path: Path) -> None:
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Spa", car="LMP2")
        recorder.start("Medium")
        result = recorder.stop()
        assert result is None

    def test_recorder_returns_none_with_single_lap_no_change(self, tmp_path: Path) -> None:
        """Snapshots on a single lap without a lap change yield no deltas."""
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Spa", car="LMP2")
        recorder.start("Medium")
        recorder.push_snapshot(_snap(lap=1, fuel=50.0, session_time=0.0))
        recorder.push_snapshot(_snap(lap=1, fuel=49.5, session_time=30.0))
        result = recorder.stop()
        assert result is None


class TestIsRecordingToggle:
    """Verify the is_recording property tracks state transitions."""

    def test_is_recording_toggle(self, tmp_path: Path) -> None:
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Nurburgring", car="GT4")

        assert recorder.is_recording is False

        recorder.start("Soft")
        assert recorder.is_recording is True

        recorder.stop()
        assert recorder.is_recording is False

    def test_snapshots_ignored_when_not_recording(self, tmp_path: Path) -> None:
        """push_snapshot should be a no-op when not recording."""
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Nurburgring", car="GT4")

        # Should not raise
        recorder.push_snapshot(_snap(lap=1, fuel=50.0, session_time=0.0))
        assert recorder.is_recording is False


class TestPitTimeMeasurement:
    """Pit stop timing from is_in_pits transitions."""

    def test_measures_pit_stop_duration(self, tmp_path: Path) -> None:
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Monza", car="GT3")
        recorder.start("soft")

        # Lap 1 on track
        recorder.push_snapshot({**_snap(1, 50.0, 0.0), "is_in_pits": False})
        recorder.push_snapshot({**_snap(1, 49.5, 30.0), "is_in_pits": False})

        # Enter pits at t=80
        recorder.push_snapshot({**_snap(1, 49.0, 80.0), "is_in_pits": True})
        recorder.push_snapshot({**_snap(1, 49.0, 95.0), "is_in_pits": True})

        # Exit pits at t=105 -> pit duration = 25s
        recorder.push_snapshot({**_snap(2, 48.0, 105.0), "is_in_pits": False})
        recorder.push_snapshot({**_snap(2, 47.5, 135.0), "is_in_pits": False})

        # Lap change to finalize
        recorder.push_snapshot({**_snap(3, 46.0, 195.0), "is_in_pits": False})

        assert recorder.measured_pit_time_s is not None
        assert abs(recorder.measured_pit_time_s - 25.0) < 0.1

    def test_no_pit_time_without_pit_stop(self, tmp_path: Path) -> None:
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Monza", car="GT3")
        recorder.start("soft")

        recorder.push_snapshot(_snap(1, 50.0, 0.0))
        recorder.push_snapshot(_snap(2, 48.0, 90.0))
        recorder.push_snapshot(_snap(3, 46.0, 180.0))

        assert recorder.measured_pit_time_s is None


class TestFuelCapacityDetection:
    """Auto-detect fuel tank capacity from telemetry."""

    def test_detects_fuel_capacity(self, tmp_path: Path) -> None:
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Monza", car="GT3")
        recorder.start("soft")

        snap = _snap(1, 50.0, 0.0)
        snap["fuel_capacity"] = 110.0
        recorder.push_snapshot(snap)

        assert recorder.detected_fuel_capacity == 110.0

    def test_no_fuel_capacity_when_missing(self, tmp_path: Path) -> None:
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Monza", car="GT3")
        recorder.start("soft")

        recorder.push_snapshot(_snap(1, 50.0, 0.0))

        assert recorder.detected_fuel_capacity is None


class TestRecorderPerLapData:
    """Recorder populates per-lap data arrays on stop()."""

    def test_record_populates_per_lap_data(self, tmp_path: Path) -> None:
        """StintRecord has non-empty lap_times_s and lap_avg_temps_c
        with length equal to lap_count after 3 recorded laps."""
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Monza", car="GT3")
        recorder.start("Soft")

        # Lap 1: temps around 80C, time 90s
        recorder.push_snapshot(_snap(lap=1, fuel=50.0, session_time=0.0, tyre_temp=80.0))
        recorder.push_snapshot(_snap(lap=1, fuel=49.5, session_time=45.0, tyre_temp=82.0))
        # Cross to lap 2 at t=90 (lap 1 time = 90s)
        recorder.push_snapshot(_snap(lap=2, fuel=48.0, session_time=90.0, tyre_temp=84.0))
        recorder.push_snapshot(_snap(lap=2, fuel=47.5, session_time=135.0, tyre_temp=86.0))
        # Cross to lap 3 at t=180 (lap 2 time = 90s)
        recorder.push_snapshot(_snap(lap=3, fuel=46.0, session_time=180.0, tyre_temp=88.0))
        recorder.push_snapshot(_snap(lap=3, fuel=45.5, session_time=225.0, tyre_temp=90.0))
        # Cross to lap 4 at t=270 (lap 3 time = 90s)
        recorder.push_snapshot(_snap(lap=4, fuel=44.5, session_time=270.0, tyre_temp=92.0))

        record = recorder.stop()

        assert record is not None
        assert record.lap_count == 3
        assert len(record.lap_times_s) == 3
        assert len(record.lap_avg_temps_c) == 3

        # Each completed lap took 90 seconds
        for lap_time in record.lap_times_s:
            assert abs(lap_time - 90.0) < 1e-6

        # Each lap had rising temps; just verify they are in a reasonable range
        for avg_temp in record.lap_avg_temps_c:
            assert 70.0 < avg_temp < 100.0


class TestPitMeasurementRecording:
    """Recorder creates PitMeasurement entries on pit entry/exit."""

    def test_pit_measurement_recorded_on_pit_exit(self, tmp_path: Path) -> None:
        """Entering pits with fuel X and exiting with fuel Y logs a
        PitMeasurement via the store."""
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Monza", car="GT3")
        recorder.start("soft")

        # Lap 1 on track
        recorder.push_snapshot({**_snap(1, 50.0, 0.0), "is_in_pits": False})
        recorder.push_snapshot({**_snap(1, 49.5, 30.0), "is_in_pits": False})

        # Enter pits at t=80, fuel=49.0
        recorder.push_snapshot({**_snap(1, 49.0, 80.0), "is_in_pits": True})
        recorder.push_snapshot({**_snap(1, 49.0, 95.0), "is_in_pits": True})

        # Exit pits at t=105, fuel=80.0 (refueled +31L) -> duration = 25s
        recorder.push_snapshot({**_snap(2, 80.0, 105.0), "is_in_pits": False})

        # The store should now have a pit measurement for "Monza"
        profile = store.get_pit_profile("Monza")
        assert len(profile.measurements) == 1
        measurement = profile.measurements[0]
        assert isinstance(measurement, PitMeasurement)
        # Pit duration ≈ 25s
        assert abs(measurement.total_time_s - 25.0) < 0.1

    def test_pit_measurement_captures_fuel_added(self, tmp_path: Path) -> None:
        """fuel_added on the measurement equals fuel_at_exit - fuel_at_entry."""
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Spa", car="LMP2")
        recorder.start("medium")

        recorder.push_snapshot({**_snap(1, 30.0, 0.0), "is_in_pits": False})
        # Enter pits at t=60 with 28L
        recorder.push_snapshot({**_snap(1, 28.0, 60.0), "is_in_pits": True})
        # Exit pits at t=90 with 95L
        recorder.push_snapshot({**_snap(2, 95.0, 90.0), "is_in_pits": False})

        profile = store.get_pit_profile("Spa")
        assert len(profile.measurements) == 1
        m = profile.measurements[0]
        assert abs(m.fuel_at_entry - 28.0) < 1e-6
        assert abs(m.fuel_at_exit - 95.0) < 1e-6
        assert abs(m.fuel_added - 67.0) < 1e-6
        assert m.compound_before == "medium"
        assert m.compound_after == "medium"
        assert m.tires_changed is False

    def test_no_pit_measurement_for_short_pit(self, tmp_path: Path) -> None:
        """A pit-in/out transition shorter than 5s is ignored."""
        store = StintStore(tmp_path / "stints.json")
        recorder = StintRecorder(store, track="Monza", car="GT3")
        recorder.start("soft")

        recorder.push_snapshot({**_snap(1, 30.0, 0.0), "is_in_pits": False})
        recorder.push_snapshot({**_snap(1, 29.5, 10.0), "is_in_pits": True})
        # Exit after only 2s -> ignored
        recorder.push_snapshot({**_snap(2, 29.5, 12.0), "is_in_pits": False})

        profile = store.get_pit_profile("Monza")
        assert len(profile.measurements) == 0
