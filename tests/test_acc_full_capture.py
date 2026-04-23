"""Tests for ACC raw-capture support."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from lap_coach_logger.adapters.acc_adapter import ACCAdapter
from lap_coach_logger.adapters.acc_shm_structs import (
    SPageFileGraphic,
    SPageFilePhysics,
    SPageFileStatic,
)
from lap_coach_logger.config.models import ACCConfig
from lap_coach_logger.writers.finalizer import SessionFinalizer
from tests.helpers import make_quality_samples


class TestACCConfig:
    def test_raw_capture_enabled_by_default(self) -> None:
        cfg = ACCConfig()
        assert cfg.enabled is True
        assert cfg.raw_capture_enabled is True


class TestACCRawAdapter:
    @staticmethod
    def _physics() -> SPageFilePhysics:
        phys = SPageFilePhysics()
        phys.packetId = 12
        phys.gas = 0.81
        phys.speedKmh = 154.2
        phys.tyreCoreTemperature[0] = 80.5
        phys.tyreContactPoint[0][0] = 1.25
        return phys

    @staticmethod
    def _graphics() -> SPageFileGraphic:
        gfx = SPageFileGraphic()
        gfx.status = 2
        gfx.session = 2
        gfx.completedLaps = 4
        gfx.trackStatus = "Green"
        return gfx

    @staticmethod
    def _static() -> SPageFileStatic:
        static = SPageFileStatic()
        static.track = "Spa"
        static.carModel = "Ferrari 296 GT3"
        static.maxFuel = 120.0
        return static

    def test_read_raw_sample_flattens_shared_memory_structs(self) -> None:
        adapter = ACCAdapter()
        adapter._connected = True

        with (
            patch.object(adapter, "_read_physics", return_value=self._physics()),
            patch.object(adapter, "_read_graphics", return_value=self._graphics()),
        ):
            row = adapter.read_raw_sample()

        assert row is not None
        assert row["acc__physics__packetId"] == 12
        assert abs(float(row["acc__physics__gas"]) - 0.81) < 1e-6
        assert row["acc__physics__tyreCoreTemperature__0"] == 80.5
        assert row["acc__physics__tyreContactPoint__0__0"] == 1.25
        assert row["acc__graphics__session"] == 2
        assert "acc__sample_timestamp_utc" in row

    def test_read_session_info_snapshot_returns_python_data(self) -> None:
        adapter = ACCAdapter()
        adapter._connected = True

        with (
            patch.object(adapter, "_read_static", return_value=self._static()),
            patch.object(adapter, "_read_graphics", return_value=self._graphics()),
        ):
            snapshot = adapter.read_session_info_snapshot()

        assert snapshot is not None
        assert snapshot["static"]["track"] == "Spa"
        assert snapshot["static"]["carModel"] == "Ferrari 296 GT3"
        assert snapshot["graphics"]["status"] == 2
        assert snapshot["graphics"]["trackStatus"] == "Green"

    def test_read_dashboard_state_exposes_live_metrics(self) -> None:
        adapter = ACCAdapter()
        adapter._connected = True
        adapter._sector_count = 3
        phys = self._physics()
        phys.fuel = 73.4
        phys.rpms = 7123
        phys.wheelsPressure[0] = 27.1
        phys.tyrewear[0] = 0.93
        phys.brakeTemp[0] = 512.0
        phys.brakeBias = 63.4
        gfx = self._graphics()
        gfx.iCurrentTime = 84250
        gfx.iLastTime = 101500
        gfx.iBestTime = 100875
        gfx.iDeltaLapTime = 625
        gfx.isDeltaPositive = 1
        gfx.currentSectorIndex = 1
        gfx.lastSectorTime = 31250
        gfx.TC = 4
        gfx.ABS = 3
        gfx.EngineMap = 6
        gfx.fuelXLap = 2.45
        gfx.fuelEstimatedLaps = 29.9
        gfx.GlobalGreen = 1

        with (
            patch.object(adapter, "_read_physics", return_value=phys),
            patch.object(adapter, "_read_graphics", return_value=gfx),
        ):
            state = adapter.read_dashboard_state()

        assert state is not None
        assert state["lap_time_s"] == 84.25
        assert state["best_lap_time_s"] == 100.875
        assert state["live_delta_s"] == 0.625
        assert state["current_sector_index"] == 2
        assert state["fuel_per_lap_l"] == pytest.approx(2.45)
        assert state["flag_state"] == "green"
        assert state["tyre_pressure_lf"] == pytest.approx(27.1)
        assert state["brake_temp_lf"] == 512.0
        assert state["brake_bias_pct"] == pytest.approx(63.4)


class TestACCFinalizerWithRawData:
    def test_finalize_with_acc_raw_outputs(self, tmp_path: Path) -> None:
        output = tmp_path / "sessions"
        output.mkdir()
        fin = SessionFinalizer(output)
        samples = make_quality_samples(100, sim="ACC", car="Ferrari 296 GT3")
        raw_samples = [
            {
                "acc__physics__packetId": i,
                "acc__physics__speedKmh": 150.0 + i,
                "acc__graphics__status": 2,
                "acc__sample_timestamp_utc": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            }
            for i in range(25)
        ]
        raw_columns = [
            "acc__graphics__status",
            "acc__physics__packetId",
            "acc__physics__speedKmh",
            "acc__sample_timestamp_utc",
        ]
        session_info = {
            "static": {"track": "Spa", "carModel": "Ferrari 296 GT3"},
            "graphics": {"status": 2, "session": 2},
        }

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = fin.finalize(
            samples,
            started_at=now,
            ended_at=now + timedelta(seconds=100),
            sim="ACC",
            track="Spa",
            session_type="Race",
            session_uid="acc-raw-uid",
            extra_metadata={"car": "Ferrari 296 GT3", "sample_rate_hz": 10.0},
            raw_capture_sim="ACC",
            raw_samples=raw_samples,
            raw_columns=raw_columns,
            raw_session_info=session_info,
        )
        assert result is not None

        assert (result / "telemetry_acc_raw.csv").exists()
        assert (result / "channels_acc_raw.json").exists()
        assert (result / "session_info_acc.json").exists()

        manifest = json.loads((result / "session.json").read_text(encoding="utf-8"))
        assert manifest["schema_version"] == 2
        # ACC raw files should appear in the bundle_files inventory
        file_names = {f["name"] for f in manifest.get("bundle_files", [])}
        assert "telemetry_acc_raw.csv" in file_names

        channels = json.loads((result / "channels_acc_raw.json").read_text(encoding="utf-8"))
        assert channels["channel_count"] == len(raw_columns)
        packet_channel = next(
            channel for channel in channels["channels"]
            if channel["column_name"] == "acc__physics__packetId"
        )
        assert packet_channel["raw_field_name"] == "physics__packetId"
        assert packet_channel["dtype"] == "int64"
