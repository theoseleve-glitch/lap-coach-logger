"""Tests for session bundle output format.

Validates that finalization produces the full bundle structure:
  session.json, telemetry.csv, laps.json, events.json, channels.json, metadata.json
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.normalization.mapper import TELEMETRY_SCHEMA_VERSION
from lap_coach_logger.writers.bundle_schema import (
    BUNDLE_SCHEMA_VERSION,
    LapRecord,
    SessionEvent,
    SessionManifest,
    compute_file_sha256,
)
from lap_coach_logger.writers.channels import build_channel_defs
from lap_coach_logger.writers.finalizer import SessionFinalizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_samples(n: int = 5) -> list[TelemetrySample]:
    return [
        TelemetrySample(sim="iRacing", speed_kph=float(i * 20), gear=i % 6)
        for i in range(n)
    ]


def _laps() -> list[LapRecord]:
    return [
        LapRecord(lap_number=1, start_session_time_s=0.0, end_session_time_s=30.0,
                  lap_time_s=30.0, out_lap=True),
        LapRecord(lap_number=2, start_session_time_s=30.0, end_session_time_s=55.0,
                  lap_time_s=25.0),
    ]


def _events() -> list[SessionEvent]:
    return [
        SessionEvent(event="recording_started", timestamp_utc="2025-01-01T00:00:00+00:00"),
        SessionEvent(event="recording_stopped", timestamp_utc="2025-01-01T00:01:00+00:00"),
    ]


# ---------------------------------------------------------------------------
# Bundle structure
# ---------------------------------------------------------------------------

class TestBundleStructure:

    def test_bundle_contains_all_files(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)
        result = fin.finalize(
            _make_samples(),
            started_at=now,
            sim="iRacing",
            track="Spa",
            session_type="Race",
            session_uid="uid-1",
            laps=_laps(),
            events=_events(),
        )
        assert result is not None
        assert (result / "session.json").exists()
        assert (result / "telemetry.csv").exists()
        assert (result / "laps.json").exists()
        assert (result / "events.json").exists()
        assert (result / "channels.json").exists()
        assert (result / "quality_report.json").exists()
        # Backward-compat shim
        assert (result / "metadata.json").exists()

    def test_no_parquet_alongside_csv(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)
        result = fin.finalize(
            _make_samples(), started_at=now, sim="x", track="y", session_type="z",
        )
        assert result is not None
        assert not (result / "telemetry.parquet").exists()


# ---------------------------------------------------------------------------
# session.json content
# ---------------------------------------------------------------------------

class TestSessionJson:

    def test_manifest_fields(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)
        result = fin.finalize(
            _make_samples(10),
            started_at=now,
            sim="iRacing",
            track="Monza",
            session_type="Qualify",
            session_uid="uid-abc",
            laps=_laps(),
            events=_events(),
            driver_name="Test Driver",
            adapter_name="IRacingAdapter",
            extra_metadata={"car": "BMW M4", "sample_rate_hz": 10.0, "dropped_samples": 1},
        )
        assert result is not None
        manifest = json.loads((result / "session.json").read_text())

        assert manifest["schema_version"] == BUNDLE_SCHEMA_VERSION
        assert manifest["telemetry_schema_version"] == TELEMETRY_SCHEMA_VERSION
        assert manifest["session_id"] == "uid-abc"
        assert manifest["sim_name"] == "iRacing"
        assert manifest["track_name"] == "Monza"
        assert manifest["car_name"] == "BMW M4"
        assert manifest["driver_name"] == "Test Driver"
        assert manifest["adapter"] == "IRacingAdapter"
        assert manifest["sample_count"] == 10
        assert manifest["dropped_sample_count"] == 1
        assert manifest["sample_rate_hz"] == 10.0
        assert manifest["telemetry_format"] == "csv"
        assert manifest["telemetry_file"] == "telemetry.csv"
        assert isinstance(manifest["telemetry_sha256"], str)
        assert len(manifest["telemetry_sha256"]) == 64  # hex SHA-256
        assert manifest["sync_status"] == "not_queued"
        assert manifest["sync_attempt_count"] == 0
        assert manifest["last_sync_attempt_at"] is None
        assert manifest["last_sync_error"] is None
        assert manifest["remote_id"] is None
        assert isinstance(manifest["bundle_hash"], str)
        assert len(manifest["bundle_hash"]) == 64
        assert manifest["quality_classification"] in {
            "accepted",
            "accepted_with_warnings",
            "needs_review",
            "rejected",
        }
        assert 0.0 <= manifest["quality_score"] <= 1.0
        assert manifest["logger_version"] is not None
        assert "started_at_utc" in manifest
        assert "ended_at_utc" in manifest
        assert manifest["duration_s"] >= 0
        assert 0.0 <= manifest["data_quality_score"] <= 1.0

    def test_telemetry_sha256_is_valid(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)
        result = fin.finalize(
            _make_samples(), started_at=now, sim="x", track="y", session_type="z",
        )
        assert result is not None
        manifest = json.loads((result / "session.json").read_text())
        expected = compute_file_sha256(result / "telemetry.csv")
        assert manifest["telemetry_sha256"] == expected


# ---------------------------------------------------------------------------
# laps.json
# ---------------------------------------------------------------------------

class TestLapsJson:

    def test_laps_written(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)
        result = fin.finalize(
            _make_samples(), started_at=now, sim="x", track="y", session_type="z",
            laps=_laps(),
        )
        assert result is not None
        laps = json.loads((result / "laps.json").read_text())
        assert len(laps) == 2
        assert laps[0]["lap_number"] == 1
        assert laps[0]["lap_time_s"] == 30.0
        assert laps[0]["out_lap"] is True
        assert laps[1]["lap_number"] == 2
        assert laps[1]["lap_time_s"] == 25.0
        assert laps[1]["out_lap"] is False

    def test_empty_laps_produces_empty_array(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)
        result = fin.finalize(
            _make_samples(), started_at=now, sim="x", track="y", session_type="z",
        )
        assert result is not None
        laps = json.loads((result / "laps.json").read_text())
        assert laps == []


# ---------------------------------------------------------------------------
# events.json
# ---------------------------------------------------------------------------

class TestEventsJson:

    def test_events_written(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)
        result = fin.finalize(
            _make_samples(), started_at=now, sim="x", track="y", session_type="z",
            events=_events(),
        )
        assert result is not None
        evts = json.loads((result / "events.json").read_text())
        assert len(evts) == 2
        assert evts[0]["event"] == "recording_started"
        assert evts[1]["event"] == "recording_stopped"

    def test_empty_events_produces_empty_array(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)
        result = fin.finalize(
            _make_samples(), started_at=now, sim="x", track="y", session_type="z",
        )
        assert result is not None
        evts = json.loads((result / "events.json").read_text())
        assert evts == []


# ---------------------------------------------------------------------------
# channels.json
# ---------------------------------------------------------------------------

class TestChannelsJson:

    def test_channels_match_schema_fields(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)
        result = fin.finalize(
            _make_samples(), started_at=now, sim="x", track="y", session_type="z",
        )
        assert result is not None
        payload = json.loads((result / "channels.json").read_text())
        assert payload["schema_version"] == TELEMETRY_SCHEMA_VERSION
        channels = payload["channels"]
        channel_names = [ch["canonical_name"] for ch in channels]
        assert channel_names == TelemetrySample.field_names()

    def test_every_channel_has_required_keys(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)
        result = fin.finalize(
            _make_samples(), started_at=now, sim="x", track="y", session_type="z",
        )
        payload = json.loads((result / "channels.json").read_text())
        channels = payload["channels"]
        for ch in channels:
            assert "canonical_name" in ch
            assert "dtype" in ch
            assert "units" in ch
            assert "missing_allowed" in ch
            assert "source_names" in ch

    def test_build_channel_defs_covers_all_fields(self) -> None:
        defs = build_channel_defs()
        assert len(defs) == len(TelemetrySample.field_names())


# ---------------------------------------------------------------------------
# metadata.json backward compatibility
# ---------------------------------------------------------------------------

class TestMetadataCompat:

    def test_metadata_json_still_written(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)
        result = fin.finalize(
            _make_samples(), started_at=now, sim="iRacing", track="Spa", session_type="Race",
            session_uid="u1",
            extra_metadata={"car": "Porsche", "sample_rate_hz": 10.0, "dropped_samples": 0},
        )
        assert result is not None
        meta = json.loads((result / "metadata.json").read_text())
        # Legacy fields still present
        assert meta["save_format"] == "csv"
        assert meta["sample_count"] == 5
        assert meta["sim"] == "iRacing"
        assert meta["bundle_schema_version"] == BUNDLE_SCHEMA_VERSION
        assert meta["sync_status"] == "not_queued"
        assert meta["sync_attempt_count"] == 0
        assert meta["last_sync_attempt_at"] is None
        assert meta["last_sync_error"] is None
        assert meta["remote_id"] is None
        assert isinstance(meta["bundle_hash"], str)
        assert len(meta["bundle_hash"]) == 64
        assert meta["quality_classification"] in {
            "accepted",
            "accepted_with_warnings",
            "needs_review",
            "rejected",
        }
        assert 0.0 <= meta["quality_score"] <= 1.0
        assert 0.0 <= meta["data_quality_score"] <= 1.0


class TestQualityReport:

    def test_quality_report_schema(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)
        result = fin.finalize(
            _make_samples(120),
            started_at=now,
            sim="iRacing",
            track="Spa",
            session_type="Race",
            extra_metadata={"car": "GT3", "sample_rate_hz": 10.0},
        )
        assert result is not None
        qr = json.loads((result / "quality_report.json").read_text())
        assert "overall_quality_score" in qr
        assert "individual_checks" in qr
        assert "warnings" in qr
        assert "rejection_reasons" in qr
        assert "recommended_classification" in qr
        assert 0.0 <= qr["overall_quality_score"] <= 1.0
        assert qr["recommended_classification"] in {
            "accepted",
            "accepted_with_warnings",
            "needs_review",
            "rejected",
        }


# ---------------------------------------------------------------------------
# Bundle schema models
# ---------------------------------------------------------------------------

class TestBundleSchemaModels:

    def test_lap_record_to_dict(self) -> None:
        lr = LapRecord(lap_number=1, start_session_time_s=0.0, end_session_time_s=30.0,
                       lap_time_s=30.0, out_lap=True)
        d = lr.to_dict()
        assert d["lap_number"] == 1
        assert d["out_lap"] is True

    def test_session_event_to_dict(self) -> None:
        ev = SessionEvent(event="test", timestamp_utc="2025-01-01T00:00:00+00:00",
                          detail={"key": "val"})
        d = ev.to_dict()
        assert d["event"] == "test"
        assert d["detail"] == {"key": "val"}

    def test_session_event_no_detail(self) -> None:
        ev = SessionEvent(event="test", timestamp_utc="2025-01-01T00:00:00+00:00")
        d = ev.to_dict()
        assert "detail" not in d

    def test_manifest_to_dict(self) -> None:
        m = SessionManifest(session_id="s1", logger_version="1.0.0")
        d = m.to_dict()
        assert d["session_id"] == "s1"
        assert d["schema_version"] == BUNDLE_SCHEMA_VERSION

    def test_compute_file_sha256(self, tmp_path: Path) -> None:
        f = tmp_path / "test.bin"
        f.write_bytes(b"hello world")
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert compute_file_sha256(f) == expected


# ---------------------------------------------------------------------------
# Parquet fallback still produces bundle
# ---------------------------------------------------------------------------

class TestParquetFallbackBundle:

    def test_bundle_with_parquet_fallback(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)

        with patch(
            "lap_coach_logger.writers.finalizer.CsvWriter.write_samples",
            side_effect=RuntimeError("csv fail"),
        ):
            result = fin.finalize(
                _make_samples(), started_at=now, sim="x", track="y", session_type="z",
                laps=_laps(),
            )

        assert result is not None
        assert (result / "telemetry.parquet").exists()
        assert (result / "session.json").exists()
        assert (result / "laps.json").exists()

        manifest = json.loads((result / "session.json").read_text())
        assert manifest["telemetry_format"] == "parquet"
        assert manifest["telemetry_file"] == "telemetry.parquet"
        assert len(manifest["telemetry_sha256"]) == 64
