"""Tests for iRacing full-capture functionality.

Covers:
  - Raw var flattening (scalar + array)
  - Session metadata flattening
  - Auto-SDK sample mode config
  - Raw channel manifest generation
  - Backward compatibility of normalized output
  - Finalizer with iRacing raw data
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from lap_coach_logger.adapters.iracing_adapter import (
    IRacingAdapter,
    _flatten_dict,
    _safe_value,
)
from lap_coach_logger.config.models import AppConfig, IRacingConfig
from lap_coach_logger.core.iracing_raw_capture import IRacingRawCapture
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.normalization.mapper import normalise_sample
from lap_coach_logger.writers.channels import build_raw_iracing_channels_payload
from lap_coach_logger.writers.finalizer import SessionFinalizer
from tests.helpers import make_quality_samples


# ---------------------------------------------------------------------------
# _safe_value
# ---------------------------------------------------------------------------


class TestSafeValue:
    def test_none(self) -> None:
        assert _safe_value(None) is None

    def test_int(self) -> None:
        assert _safe_value(42) == 42

    def test_float(self) -> None:
        assert _safe_value(3.14) == 3.14

    def test_nan_becomes_none(self) -> None:
        assert _safe_value(float("nan")) is None

    def test_inf_becomes_none(self) -> None:
        assert _safe_value(float("inf")) is None
        assert _safe_value(float("-inf")) is None

    def test_string(self) -> None:
        assert _safe_value("hello") == "hello"

    def test_bool(self) -> None:
        assert _safe_value(True) is True

    def test_list(self) -> None:
        assert _safe_value([1.0, float("nan"), 3]) == [1.0, None, 3]


# ---------------------------------------------------------------------------
# _flatten_dict (session metadata flattening)
# ---------------------------------------------------------------------------


class TestFlattenDict:
    def test_simple_dict(self) -> None:
        result: dict[str, Any] = {}
        _flatten_dict({"TrackName": "spa", "TrackID": 47}, "session__WeekendInfo", result)
        assert result == {
            "session__WeekendInfo__TrackName": "spa",
            "session__WeekendInfo__TrackID": 47,
        }

    def test_nested_dict(self) -> None:
        result: dict[str, Any] = {}
        _flatten_dict(
            {"WeekendInfo": {"TrackName": "spa", "TrackLength": "3.5 km"}},
            "session",
            result,
        )
        assert result["session__WeekendInfo__TrackName"] == "spa"
        assert result["session__WeekendInfo__TrackLength"] == "3.5 km"

    def test_list_flattening(self) -> None:
        """Lists should flatten with numeric indices (SessionInfo.Sessions[0]...)."""
        result: dict[str, Any] = {}
        _flatten_dict(
            {"Sessions": [{"SessionType": "Practice"}, {"SessionType": "Race"}]},
            "session__SessionInfo",
            result,
        )
        assert result["session__SessionInfo__Sessions__0__SessionType"] == "Practice"
        assert result["session__SessionInfo__Sessions__1__SessionType"] == "Race"

    def test_nan_leaf_becomes_none(self) -> None:
        result: dict[str, Any] = {}
        _flatten_dict({"val": float("nan")}, "prefix", result)
        assert result["prefix__val"] is None

    def test_deep_nesting(self) -> None:
        result: dict[str, Any] = {}
        _flatten_dict({"a": {"b": {"c": 99}}}, "x", result)
        assert result["x__a__b__c"] == 99


# ---------------------------------------------------------------------------
# Raw var flattening (simulated)
# ---------------------------------------------------------------------------


class TestRawVarFlattening:
    """Test the pattern used in IRacingAdapter.read_raw_sample for scalar and array vars."""

    def _flatten_row(self, var_headers: list[dict], values: dict[str, Any]) -> dict[str, Any]:
        """Simulate the read_raw_sample flattening logic."""
        row: dict[str, Any] = {}
        for vh in var_headers:
            name = vh["name"]
            count = vh["count"]
            val = values.get(name)
            if count == 1:
                row[f"irsdk__{name}"] = _safe_value(val)
            else:
                if isinstance(val, (list, tuple)):
                    for i, v in enumerate(val):
                        row[f"irsdk__{name}__{i}"] = _safe_value(v)
                    for i in range(len(val), count):
                        row[f"irsdk__{name}__{i}"] = None
                else:
                    row[f"irsdk__{name}__0"] = _safe_value(val)
                    for i in range(1, count):
                        row[f"irsdk__{name}__{i}"] = None
        return row

    def test_scalar_var(self) -> None:
        headers = [{"name": "Speed", "count": 1}]
        row = self._flatten_row(headers, {"Speed": 42.5})
        assert row == {"irsdk__Speed": 42.5}

    def test_array_var(self) -> None:
        headers = [{"name": "CarIdxLapDistPct", "count": 3}]
        row = self._flatten_row(headers, {"CarIdxLapDistPct": [0.1, 0.5, 0.9]})
        assert row == {
            "irsdk__CarIdxLapDistPct__0": 0.1,
            "irsdk__CarIdxLapDistPct__1": 0.5,
            "irsdk__CarIdxLapDistPct__2": 0.9,
        }

    def test_array_var_with_nan(self) -> None:
        headers = [{"name": "CarIdxLap", "count": 3}]
        row = self._flatten_row(headers, {"CarIdxLap": [1, float("nan"), 3]})
        assert row["irsdk__CarIdxLap__0"] == 1
        assert row["irsdk__CarIdxLap__1"] is None
        assert row["irsdk__CarIdxLap__2"] == 3

    def test_array_var_shorter_than_count(self) -> None:
        headers = [{"name": "X", "count": 4}]
        row = self._flatten_row(headers, {"X": [1, 2]})
        assert row["irsdk__X__0"] == 1
        assert row["irsdk__X__1"] == 2
        assert row["irsdk__X__2"] is None
        assert row["irsdk__X__3"] is None

    def test_missing_var_becomes_none(self) -> None:
        headers = [{"name": "Missing", "count": 1}]
        row = self._flatten_row(headers, {})
        assert row == {"irsdk__Missing": None}

    def test_mixed_scalar_and_array(self) -> None:
        headers = [
            {"name": "Speed", "count": 1},
            {"name": "Arr", "count": 2},
        ]
        row = self._flatten_row(headers, {"Speed": 100.0, "Arr": [10, 20]})
        assert row["irsdk__Speed"] == 100.0
        assert row["irsdk__Arr__0"] == 10
        assert row["irsdk__Arr__1"] == 20

    def test_st_array_var(self) -> None:
        """_ST vars have count=6 in iRacing."""
        headers = [{"name": "LatAccel_ST", "count": 6}]
        vals = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        row = self._flatten_row(headers, {"LatAccel_ST": vals})
        for i, v in enumerate(vals):
            assert row[f"irsdk__LatAccel_ST__{i}"] == v


# ---------------------------------------------------------------------------
# IRacingRawCapture
# ---------------------------------------------------------------------------


class TestIRacingRawCapture:
    def test_append_and_count(self) -> None:
        rc = IRacingRawCapture()
        assert rc.raw_sample_count == 0
        rc.append_raw_sample({"irsdk__Speed": 100.0, "irsdk__RPM": 5000.0})
        rc.append_raw_sample({"irsdk__Speed": 110.0, "irsdk__RPM": 5100.0})
        assert rc.raw_sample_count == 2

    def test_reset_clears(self) -> None:
        rc = IRacingRawCapture()
        rc.append_raw_sample({"x": 1})
        rc.set_session_info_snapshot({"a": "b"})
        rc.reset()
        assert rc.raw_sample_count == 0
        assert rc.session_info_snapshot is None

    def test_column_names_union(self) -> None:
        rc = IRacingRawCapture()
        rc.append_raw_sample({"a": 1, "b": 2})
        rc.append_raw_sample({"a": 3, "c": 4})
        cols = rc.get_raw_column_names()
        assert sorted(cols) == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Config: sample_mode
# ---------------------------------------------------------------------------


class TestIRacingConfig:
    def test_default_sample_mode(self) -> None:
        cfg = IRacingConfig()
        assert cfg.sample_mode == "auto_sdk"
        assert cfg.raw_capture_enabled is True

    def test_manual_mode(self) -> None:
        cfg = IRacingConfig(sample_mode="manual")
        assert cfg.sample_mode == "manual"

    def test_app_config_defaults(self) -> None:
        app = AppConfig()
        assert isinstance(app.iracing, IRacingConfig)
        assert app.iracing.sample_mode == "auto_sdk"

    def test_app_config_from_dict(self) -> None:
        d = {"iracing": {"sample_mode": "manual", "raw_capture_enabled": False}}
        app = AppConfig.from_dict(d)
        assert isinstance(app.iracing, IRacingConfig)
        assert app.iracing.sample_mode == "manual"
        assert app.iracing.raw_capture_enabled is False

    def test_validation_valid_modes(self) -> None:
        app = AppConfig()
        app.iracing.sample_mode = "auto_sdk"
        errors = app.validate()
        assert not any("sample_mode" in e for e in errors)

    def test_validation_invalid_mode(self) -> None:
        app = AppConfig()
        app.iracing.sample_mode = "invalid_mode"
        errors = app.validate()
        assert any("sample_mode" in e for e in errors)


# ---------------------------------------------------------------------------
# Raw channel manifest
# ---------------------------------------------------------------------------


class TestRawChannelsPayload:
    def test_basic(self) -> None:
        payload = build_raw_iracing_channels_payload(
            ["irsdk__Speed", "irsdk__RPM", "irsdk__CarIdxLap__0"]
        )
        assert payload["channel_count"] == 3
        channels = payload["channels"]
        names = [c["column_name"] for c in channels]
        assert "irsdk__Speed" in names
        assert "irsdk__CarIdxLap__0" in names

    def test_with_var_schema(self) -> None:
        schema = [
            {"name": "Speed", "unit": "m/s", "desc": "Car speed", "count": 1, "type": "5"},
            {"name": "CarIdxLap", "unit": "", "desc": "Lap count", "count": 64, "type": "2"},
        ]
        payload = build_raw_iracing_channels_payload(
            ["irsdk__Speed", "irsdk__CarIdxLap__0", "irsdk__CarIdxLap__1"],
            var_schema=schema,
        )
        assert payload["channel_count"] == 3
        speed_ch = [c for c in payload["channels"] if c["column_name"] == "irsdk__Speed"][0]
        assert speed_ch["units"] == "m/s"
        assert speed_ch["description"] == "Car speed"
        assert speed_ch["is_array_element"] is False

        idx_ch = [c for c in payload["channels"] if c["column_name"] == "irsdk__CarIdxLap__0"][0]
        assert idx_ch["is_array_element"] is True


# ---------------------------------------------------------------------------
# Normalized output backward compatibility
# ---------------------------------------------------------------------------


class TestNormalizedBackwardCompat:
    """Ensure the existing normalized TelemetrySample + normalise_sample still works."""

    def test_iracing_normalise(self) -> None:
        raw = {
            "SessionTime": 12.5,
            "Lap": 2,
            "Speed": 45.0,
            "Throttle": 0.8,
            "Brake": 0.0,
            "Gear": 4,
            "RPM": 6200.0,
            "LapDist": 1500.0,
            "LapDistPct": 0.42,
            "SteeringWheelAngle": 0.1,
            "Clutch": 1.0,
            "Lat": 10.0,
            "Alt": 5.0,
            "Lon": 20.0,
            "Yaw": 1.57,
            "Pitch": 0.01,
            "Roll": 0.02,
            "LongAccel": 0.3,
            "LatAccel": -0.2,
            "LFtempCL": 85.0,
            "RFtempCL": 86.0,
            "LRtempCL": 83.0,
            "RRtempCL": 84.0,
            "FuelLevel": 42.0,
            "WaterTemp": 88.0,
            "OilTemp": 95.0,
            "TrackTempCrew": 32.0,
            "AirTemp": 24.0,
            "IsOnTrack": True,
            "OnPitRoad": False,
            "dcABS": 3.0,
            "dcTractionControl": 5.0,
        }
        sample = normalise_sample(raw, sim="iRacing")
        assert sample.sim == "iRacing"
        assert sample.session_time_s == 12.5
        assert sample.lap_number == 2
        assert sample.gear == 4
        # Speed was m/s → kph
        assert sample.speed_kph is not None
        assert abs(sample.speed_kph - 45.0 * 3.6) < 0.01
        assert sample.throttle_pct == 0.8
        assert sample.is_on_track is True
        assert sample.is_in_pits is False

    def test_field_names_unchanged(self) -> None:
        """Existing TelemetrySample fields must be present."""
        expected = {
            "timestamp_utc", "sim", "session_uid", "session_time_s",
            "lap_number", "lap_distance_m", "lap_dist_pct", "speed_kph",
            "throttle_pct", "brake_pct", "steering_deg", "clutch_pct",
            "gear", "rpm", "abs_level", "tc_level",
            "world_pos_x", "world_pos_y", "world_pos_z",
            "yaw_deg", "pitch", "roll", "long_accel_g", "lat_accel_g",
            "tyre_temp_lf", "tyre_temp_rf", "tyre_temp_lr", "tyre_temp_rr",
            "fuel_level", "fuel_capacity", "water_temp", "oil_temp",
            "track_temp_c", "air_temp_c", "is_on_track", "is_in_pits",
            "track_name", "car_name", "session_type", "raw_source_timestamp",
        }
        actual = set(TelemetrySample.field_names())
        assert expected.issubset(actual), f"Missing fields: {expected - actual}"


# ---------------------------------------------------------------------------
# Finalizer with iRacing raw data
# ---------------------------------------------------------------------------


class TestFinalizerWithRawData:
    """Test that the finalizer writes the new iRacing output files."""

    def test_finalize_with_raw_data(self, tmp_path: Path) -> None:
        output = tmp_path / "sessions"
        output.mkdir()
        fin = SessionFinalizer(output)
        samples = make_quality_samples(100)
        raw_samples = [
            {"irsdk__Speed": 100.0 + i, "irsdk__RPM": 5000.0 + i * 10}
            for i in range(100)
        ]
        raw_columns = ["irsdk__RPM", "irsdk__Speed"]
        session_info = {
            "session__WeekendInfo__TrackName": "spa",
            "session__WeekendInfo__TrackID": 47,
        }
        catalogs = {
            "localserver_track_fields": {
                "source_path": "test.json",
                "data": ["field1", "field2"],
                "count": 2,
            },
        }

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = fin.finalize(
            samples,
            started_at=now,
            ended_at=now + timedelta(seconds=100),
            sim="iRacing",
            track="Spa",
            session_type="Race",
            session_uid="test-raw-uid",
            extra_metadata={"car": "GT3", "sample_rate_hz": 60.0},
            iracing_raw_samples=raw_samples,
            iracing_raw_columns=raw_columns,
            iracing_session_info=session_info,
            iracing_catalogs=catalogs,
        )
        assert result is not None

        # Check new files exist
        assert (result / "telemetry_iracing_raw.csv").exists()
        assert (result / "channels_iracing_raw.json").exists()
        assert (result / "session_info_iracing.json").exists()
        assert (result / "iracing_catalogs.json").exists()

        # Check session.json has v2 structure with iRacing raw files in bundle_files
        with open(result / "session.json", encoding="utf-8") as f:
            manifest = json.load(f)
        assert manifest["schema_version"] == 2
        # iRacing raw files should be present in the bundle_files inventory
        file_names = {f["name"] for f in manifest.get("bundle_files", [])}
        assert "telemetry_iracing_raw.csv" in file_names

        # Existing files still present
        assert (result / "telemetry.csv").exists() or (result / "telemetry.parquet").exists()
        assert (result / "channels.json").exists()
        assert (result / "session.json").exists()
        assert (result / "laps.json").exists()
        assert (result / "events.json").exists()

    def test_finalize_without_raw_data(self, tmp_path: Path) -> None:
        """Without raw data, new files should NOT be written — backward compat."""
        output = tmp_path / "sessions"
        output.mkdir()
        fin = SessionFinalizer(output)
        samples = make_quality_samples(100)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = fin.finalize(
            samples,
            started_at=now,
            ended_at=now + timedelta(seconds=100),
            sim="iRacing",
            track="Spa",
            session_type="Race",
            session_uid="test-no-raw",
            extra_metadata={"car": "GT3", "sample_rate_hz": 10.0},
        )
        assert result is not None
        # New files should NOT exist
        assert not (result / "telemetry_iracing_raw.csv").exists()
        assert not (result / "channels_iracing_raw.json").exists()
        assert not (result / "session_info_iracing.json").exists()
        assert not (result / "iracing_catalogs.json").exists()
        # But old files should exist
        assert (result / "channels.json").exists()
        assert (result / "session.json").exists()

    def test_raw_csv_content(self, tmp_path: Path) -> None:
        """Verify the raw CSV has all expected columns and correct row count."""
        import csv

        output = tmp_path / "sessions"
        output.mkdir()
        fin = SessionFinalizer(output)
        samples = make_quality_samples(50)
        raw = [
            {"irsdk__Speed": 100.0, "irsdk__CarIdxLap__0": 1, "irsdk__CarIdxLap__1": 2}
            for _ in range(50)
        ]
        cols = ["irsdk__CarIdxLap__0", "irsdk__CarIdxLap__1", "irsdk__Speed"]
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = fin.finalize(
            samples,
            started_at=now,
            ended_at=now + timedelta(seconds=50),
            sim="iRacing",
            track="Spa",
            session_type="Race",
            session_uid="csv-check",
            extra_metadata={"car": "GT3", "sample_rate_hz": 60.0},
            iracing_raw_samples=raw,
            iracing_raw_columns=cols,
        )
        assert result is not None
        csv_path = result / "telemetry_iracing_raw.csv"
        assert csv_path.exists()
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 50
        assert set(reader.fieldnames or []) == set(cols)


# ---------------------------------------------------------------------------
# Auto-SDK sample mode detection
# ---------------------------------------------------------------------------


class TestAutoSdkSampleMode:
    """Test that auto_sdk mode config is detected by the coordinator."""

    def test_auto_sdk_is_default_for_iracing(self) -> None:
        app = AppConfig()
        assert isinstance(app.iracing, IRacingConfig)
        assert app.iracing.sample_mode == "auto_sdk"

    def test_manual_mode_preserves_interval(self) -> None:
        app = AppConfig()
        app.iracing.sample_mode = "manual"
        assert app.sample_interval_s == 0.1  # unchanged default

    def test_iracing_config_inherits_sim_config(self) -> None:
        """IRacingConfig should still have the enabled field."""
        cfg = IRacingConfig(enabled=False, sample_mode="auto_sdk")
        assert cfg.enabled is False
        assert cfg.sample_mode == "auto_sdk"
