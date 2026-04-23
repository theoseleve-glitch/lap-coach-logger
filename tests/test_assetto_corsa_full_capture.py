"""Tests for classic Assetto Corsa full-capture support."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from lap_coach_logger.adapters.ac_shm_structs import (
    SPageFileGraphic,
    SPageFilePhysics,
    SPageFileStatic,
)
from lap_coach_logger.adapters.assetto_corsa_adapter import AssettoCorsaAdapter
from lap_coach_logger.config.models import AssettoCorsaConfig
from lap_coach_logger.writers.finalizer import SessionFinalizer
from tests.helpers import make_quality_samples


class TestAssettoCorsaConfig:
    def test_raw_capture_enabled_by_default(self) -> None:
        cfg = AssettoCorsaConfig()
        assert cfg.enabled is True
        assert cfg.raw_capture_enabled is True


class TestAssettoCorsaRawAdapter:
    @staticmethod
    def _physics() -> SPageFilePhysics:
        phys = SPageFilePhysics()
        phys.packetId = 17
        phys.gas = 0.73
        phys.speedKmh = 188.4
        phys.tyreCoreTemperature[0] = 83.5
        phys.velocity[0] = 12.5
        return phys

    @staticmethod
    def _graphics() -> SPageFileGraphic:
        gfx = SPageFileGraphic()
        gfx.status = 2
        gfx.session = 2
        gfx.completedLaps = 6
        gfx.currentTime = "01:44.822"
        return gfx

    @staticmethod
    def _static() -> SPageFileStatic:
        static = SPageFileStatic()
        static.track = "spa"
        static.trackConfiguration = "gp"
        static.carModel = "ks_porsche_911_gt3_r_2016"
        static.maxFuel = 100.0
        return static

    def test_read_raw_sample_flattens_shared_memory_structs(self) -> None:
        adapter = AssettoCorsaAdapter()
        adapter._connected = True

        with (
            patch.object(adapter, "_read_physics", return_value=self._physics()),
            patch.object(adapter, "_read_graphics", return_value=self._graphics()),
        ):
            row = adapter.read_raw_sample()

        assert row is not None
        assert row["ac__physics__packetId"] == 17
        assert abs(float(row["ac__physics__gas"]) - 0.73) < 1e-6
        assert row["ac__physics__tyreCoreTemperature__0"] == 83.5
        assert row["ac__graphics__session"] == 2
        assert "ac__sample_timestamp_utc" in row

    def test_read_session_info_snapshot_returns_python_data(self) -> None:
        adapter = AssettoCorsaAdapter()
        adapter._connected = True

        with (
            patch.object(adapter, "_read_static", return_value=self._static()),
            patch.object(adapter, "_read_graphics", return_value=self._graphics()),
        ):
            snapshot = adapter.read_session_info_snapshot()

        assert snapshot is not None
        assert snapshot["static"]["track"] == "spa"
        assert snapshot["static"]["trackConfiguration"] == "gp"
        assert snapshot["graphics"]["status"] == 2
        assert snapshot["graphics"]["currentTime"] == "01:44.822"

    def test_read_dashboard_state_exposes_live_metrics(self) -> None:
        adapter = AssettoCorsaAdapter()
        adapter._connected = True
        adapter._sector_count = 3
        phys = self._physics()
        phys.fuel = 41.2
        phys.wheelsPressure[0] = 26.8
        phys.tyreWear[0] = 0.91
        phys.brakeTemp[0] = 488.0
        phys.tc = 2.0
        phys.abs = 4.0
        gfx = self._graphics()
        gfx.iCurrentTime = 91600
        gfx.iLastTime = 102250
        gfx.iBestTime = 101800
        gfx.currentSectorIndex = 2
        gfx.lastSectorTime = 64875
        gfx.flag = 3

        with (
            patch.object(adapter, "_read_physics", return_value=phys),
            patch.object(adapter, "_read_graphics", return_value=gfx),
        ):
            state = adapter.read_dashboard_state()

        assert state is not None
        assert state["lap_time_s"] == 91.6
        assert state["best_lap_time_s"] == 101.8
        assert state["current_sector_index"] == 3
        assert state["last_sector_time_s"] == 64.875
        assert state["flag_state"] == "flag_3"
        assert state["tyre_pressure_lf"] == pytest.approx(26.8)
        assert state["brake_temp_lf"] == 488.0
        assert state["tc_level"] == 2.0
        assert state["abs_level"] == 4.0


class TestAssettoCorsaFinalizerWithRawData:
    def test_finalize_with_assetto_corsa_raw_outputs(self, tmp_path: Path) -> None:
        output = tmp_path / "sessions"
        output.mkdir()
        fin = SessionFinalizer(output)
        samples = make_quality_samples(
            100,
            sim="Assetto Corsa",
            track="Spa (GP)",
            car="Porsche 911 GT3 R 2016",
        )
        raw_samples = [
            {
                "ac__physics__packetId": i,
                "ac__physics__speedKmh": 180.0 + i,
                "ac__graphics__status": 2,
                "ac__sample_timestamp_utc": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            }
            for i in range(25)
        ]
        raw_columns = [
            "ac__graphics__status",
            "ac__physics__packetId",
            "ac__physics__speedKmh",
            "ac__sample_timestamp_utc",
        ]
        session_info = {
            "static": {"track": "spa", "trackConfiguration": "gp", "carModel": "ks_porsche_911_gt3_r_2016"},
            "graphics": {"status": 2, "session": 2},
        }

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = fin.finalize(
            samples,
            started_at=now,
            ended_at=now + timedelta(seconds=100),
            sim="Assetto Corsa",
            track="Spa (GP)",
            session_type="Race",
            session_uid="ac-raw-uid",
            extra_metadata={"car": "Porsche 911 GT3 R 2016", "sample_rate_hz": 10.0},
            raw_capture_sim="Assetto Corsa",
            raw_samples=raw_samples,
            raw_columns=raw_columns,
            raw_session_info=session_info,
        )
        assert result is not None

        assert (result / "telemetry_assetto_corsa_raw.csv").exists()
        assert (result / "channels_assetto_corsa_raw.json").exists()
        assert (result / "session_info_assetto_corsa.json").exists()

        manifest = json.loads((result / "session.json").read_text(encoding="utf-8"))
        assert manifest["schema_version"] == 2
        # Assetto Corsa raw files should appear in the bundle_files inventory
        file_names = {f["name"] for f in manifest.get("bundle_files", [])}
        assert "telemetry_assetto_corsa_raw.csv" in file_names

        channels = json.loads((result / "channels_assetto_corsa_raw.json").read_text(encoding="utf-8"))
        assert channels["channel_count"] == len(raw_columns)
        packet_channel = next(
            channel for channel in channels["channels"]
            if channel["column_name"] == "ac__physics__packetId"
        )
        assert packet_channel["raw_field_name"] == "physics__packetId"
        assert packet_channel["dtype"] == "int64"
