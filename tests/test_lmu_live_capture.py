"""Tests for live Le Mans Ultimate shared-memory capture support."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from lap_coach_logger.adapters.lmu_adapter import LMUAdapter
from lap_coach_logger.adapters.lmu_shm_structs import SharedMemoryLayout
from lap_coach_logger.config.models import AppConfig, LMUConfig
from lap_coach_logger.writers.finalizer import SessionFinalizer
from tests.helpers import make_quality_samples


def _build_layout() -> SharedMemoryLayout:
    layout = SharedMemoryLayout()
    data = layout.data

    data.generic.gameVersion = 20250328
    data.generic.appInfo.mOptionsLocation = 3

    data.scoring.scoringInfo.mTrackName = b"Circuit de la Sarthe"
    data.scoring.scoringInfo.mSession = 10
    data.scoring.scoringInfo.mCurrentET = 123.4
    data.scoring.scoringInfo.mLapDist = 13626.0
    data.scoring.scoringInfo.mNumVehicles = 3
    data.scoring.scoringInfo.mInRealtime = True
    data.scoring.scoringInfo.mPlayerName = b"Test Driver"
    data.scoring.scoringInfo.mAmbientTemp = 21.5
    data.scoring.scoringInfo.mTrackTemp = 29.0

    player_scoring = data.scoring.vehScoringInfo[1]
    player_scoring.mID = 7
    player_scoring.mIsPlayer = True
    player_scoring.mDriverName = b"Test Driver"
    player_scoring.mVehicleName = b"Toyota GR010"
    player_scoring.mLapDist = 6813.0
    player_scoring.mInPits = False
    player_scoring.mPitState = 0
    player_scoring.mTotalLaps = 4
    player_scoring.mPlace = 2

    data.telemetry.activeVehicles = 3
    data.telemetry.playerVehicleIdx = 1
    data.telemetry.playerHasVehicle = True

    player_telem = data.telemetry.telemInfo[1]
    player_telem.mID = 7
    player_telem.mElapsedTime = 123.4
    player_telem.mLapNumber = 5
    player_telem.mVehicleName = b"Toyota GR010"
    player_telem.mTrackName = b"Circuit de la Sarthe"
    player_telem.mPos.x = 100.0
    player_telem.mPos.y = 2.5
    player_telem.mPos.z = 250.0
    player_telem.mLocalVel.x = 1.0
    player_telem.mLocalVel.y = 0.0
    player_telem.mLocalVel.z = -69.0
    player_telem.mLocalAccel.x = 3.0
    player_telem.mLocalAccel.z = -4.5
    player_telem.mGear = 4
    player_telem.mEngineRPM = 7200.0
    player_telem.mEngineWaterTemp = 91.0
    player_telem.mEngineOilTemp = 102.0
    player_telem.mFilteredThrottle = 0.82
    player_telem.mFilteredBrake = 0.08
    player_telem.mFilteredClutch = 0.02
    player_telem.mFilteredSteering = 0.25
    player_telem.mFuel = 41.5
    player_telem.mFuelCapacity = 90.0
    player_telem.mPhysicalSteeringWheelRange = 360.0
    player_telem.mWheel[0].mTemperature[1] = 356.15
    player_telem.mWheel[1].mTemperature[1] = 357.15
    player_telem.mWheel[2].mTemperature[1] = 354.15
    player_telem.mWheel[3].mTemperature[1] = 355.15

    return layout


class TestLMUConfig:
    def test_raw_capture_enabled_by_default(self) -> None:
        cfg = LMUConfig()
        assert cfg.enabled is True
        assert cfg.raw_capture_enabled is True

    def test_app_config_from_dict_roundtrips_lmu(self) -> None:
        app = AppConfig.from_dict({"lmu": {"enabled": False, "raw_capture_enabled": False}})
        assert app.lmu.enabled is False
        assert app.lmu.raw_capture_enabled is False


class TestLMULiveAdapter:
    def test_is_session_active_and_normalizes_live_sample(self) -> None:
        adapter = LMUAdapter()
        adapter._connected = True
        layout = _build_layout()

        with patch.object(adapter, "_read_layout", return_value=layout):
            assert adapter.is_session_active() is True
            sample = adapter.read_sample()

        assert sample is not None
        assert sample.sim == "Le Mans Ultimate"
        assert sample.track_name == "Circuit de la Sarthe"
        assert sample.car_name == "Toyota GR010"
        assert sample.session_type == "race"
        assert sample.lap_number == 5
        assert sample.lap_distance_m == 6813.0
        assert sample.lap_dist_pct == 0.5
        assert sample.is_in_pits is False
        assert sample.fuel_capacity == 90.0
        assert round(sample.tyre_temp_lf or 0.0, 2) == 83.0
        assert sample.world_pos_x == 100.0

    def test_read_raw_sample_and_session_snapshot(self) -> None:
        adapter = LMUAdapter()
        adapter._connected = True
        layout = _build_layout()

        with patch.object(adapter, "_read_layout", return_value=layout):
            row = adapter.read_raw_sample()
            snapshot = adapter.read_session_info_snapshot()

        assert row is not None
        assert row["lmu__player_vehicle_idx"] == 1
        assert row["lmu__player_telemetry__mVehicleName"] == "Toyota GR010"
        assert row["lmu__scoring_info__mTrackName"] == "Circuit de la Sarthe"
        assert "lmu__sample_timestamp_utc" in row

        assert snapshot is not None
        assert snapshot["active_vehicles"] == 3
        assert snapshot["scoring_info"]["mTrackName"] == "Circuit de la Sarthe"
        assert snapshot["player_telemetry"]["mVehicleName"] == "Toyota GR010"

    def test_read_dashboard_state_exposes_live_metrics(self) -> None:
        adapter = LMUAdapter()
        adapter._connected = True
        layout = _build_layout()
        player_scoring = layout.data.scoring.vehScoringInfo[1]
        player_scoring.mTimeIntoLap = 82.4
        player_scoring.mBestLapTime = 220.75
        player_scoring.mLastSector1 = 34.5
        player_scoring.mLastSector2 = 41.25
        player_scoring.mLastLapTime = 118.4
        player_scoring.mUnderYellow = True
        layout.data.scoring.scoringInfo.mGamePhase = 6
        layout.data.telemetry.telemInfo[1].mRearBrakeBias = 59.2
        layout.data.telemetry.telemInfo[1].mWheel[0].mPressure = 181.3
        layout.data.telemetry.telemInfo[1].mWheel[0].mWear = 0.88
        layout.data.telemetry.telemInfo[1].mWheel[0].mBrakeTemp = 503.0

        with patch.object(adapter, "_read_layout", return_value=layout):
            state = adapter.read_dashboard_state()

        assert state is not None
        assert state["lap_time_s"] == 82.4
        assert state["best_lap_time_s"] == 220.75
        assert state["sector_1_time_s"] == 34.5
        assert state["sector_2_time_s"] == 41.25
        assert round(float(state["sector_3_time_s"]), 2) == 42.65
        assert state["session_status"] == "full_course_yellow"
        assert state["flag_state"] == "yellow"
        assert state["tyre_pressure_lf"] == 181.3
        assert state["tyre_wear_lf"] == 0.88
        assert state["brake_temp_lf"] == 503.0
        assert state["brake_bias_pct"] == 59.2


class TestLMUFinalizerWithRawData:
    def test_finalize_with_lmu_raw_outputs(self, tmp_path: Path) -> None:
        output = tmp_path / "sessions"
        output.mkdir()
        fin = SessionFinalizer(output)
        samples = make_quality_samples(
            100,
            sim="Le Mans Ultimate",
            track="Circuit de la Sarthe",
            car="Toyota GR010",
        )
        raw_samples = [
            {
                "lmu__player_vehicle_idx": 1,
                "lmu__player_telemetry__mEngineRPM": 7000.0 + i,
                "lmu__scoring_info__mCurrentET": float(i),
                "lmu__sample_timestamp_utc": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            }
            for i in range(25)
        ]
        raw_columns = [
            "lmu__player_vehicle_idx",
            "lmu__player_telemetry__mEngineRPM",
            "lmu__scoring_info__mCurrentET",
            "lmu__sample_timestamp_utc",
        ]
        session_info = {
            "scoring_info": {"mTrackName": "Circuit de la Sarthe", "mSession": 10},
            "player_telemetry": {"mVehicleName": "Toyota GR010"},
        }

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = fin.finalize(
            samples,
            started_at=now,
            ended_at=now + timedelta(seconds=100),
            sim="Le Mans Ultimate",
            track="Circuit de la Sarthe",
            session_type="Race",
            session_uid="lmu-raw-uid",
            extra_metadata={"car": "Toyota GR010", "sample_rate_hz": 10.0},
            raw_capture_sim="LMU",
            raw_samples=raw_samples,
            raw_columns=raw_columns,
            raw_session_info=session_info,
        )
        assert result is not None

        assert (result / "telemetry_lmu_raw.csv").exists()
        assert (result / "channels_lmu_raw.json").exists()
        assert (result / "session_info_lmu.json").exists()

        manifest = json.loads((result / "session.json").read_text(encoding="utf-8"))
        assert manifest["schema_version"] == 2
        # LMU raw files should appear in the bundle_files inventory
        file_names = {f["name"] for f in manifest.get("bundle_files", [])}
        assert "telemetry_lmu_raw.csv" in file_names
