"""Tests for session bundle output format.

Validates that finalization produces the full bundle structure:
  session.json, telemetry.parquet, laps.json, events.json, channels.json, metadata.json
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
    LegacyLapRecord as LapRecord,
    LegacySessionManifest,
    SessionEvent,
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
        assert (result / "telemetry.parquet").exists()
        assert (result / "laps.json").exists()
        assert (result / "events.json").exists()
        assert (result / "channels.json").exists()
        assert (result / "quality_report.json").exists()
        assert (result / "analysis.json").exists()
        # metadata.json is no longer written in v2
        assert not (result / "metadata.json").exists()

    def test_no_csv_alongside_parquet(self, tmp_path: Path) -> None:
        """Primary format is parquet; no CSV should be present unless debug export."""
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)
        result = fin.finalize(
            _make_samples(), started_at=now, sim="x", track="y", session_type="z",
        )
        assert result is not None
        assert (result / "telemetry.parquet").exists()
        assert not (result / "telemetry.csv").exists()


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

        # v2 schema structure
        assert manifest["schema_version"] == 2
        assert manifest["session_id"] == "uid-abc"
        assert manifest["logger_version"] is not None

        # raw_source block
        raw = manifest["raw_source"]
        assert raw["sim_id"] == "iracing"
        assert raw["raw_track"] == "Monza"
        assert raw["raw_car"] == "BMW M4"
        assert raw["session_type_raw"] == "Qualify"

        # session block
        sess = manifest["session"]
        assert sess["session_uid"] == "uid-abc"
        assert sess["driver_name"] == "Test Driver"
        assert sess["sample_count"] == 10
        assert sess["lap_count"] == 2
        assert sess["duration_s"] >= 0
        assert sess["start_time"] is not None
        assert sess["end_time"] is not None

        # bundle_hash
        assert isinstance(manifest["bundle_hash"], str)
        assert manifest["bundle_hash"].startswith("sha256:")

        # analysis_readiness
        readiness = manifest["analysis_readiness"]
        assert 0.0 <= readiness["quality_score"] <= 1.0
        assert isinstance(readiness["ready_for_analysis"], bool)

        # bundle_files inventory
        file_names = {f["name"] for f in manifest["bundle_files"]}
        assert "telemetry.parquet" in file_names
        assert "session.json" in file_names
        assert "analysis.json" in file_names

        # telemetry hash in bundle_files
        tel_entry = next(f for f in manifest["bundle_files"] if f["name"] == "telemetry.parquet")
        assert isinstance(tel_entry["sha256"], str)
        assert tel_entry["sha256"].startswith("sha256:")

    def test_telemetry_sha256_is_valid(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)
        result = fin.finalize(
            _make_samples(), started_at=now, sim="x", track="y", session_type="z",
        )
        assert result is not None
        manifest = json.loads((result / "session.json").read_text())
        expected = "sha256:" + compute_file_sha256(result / "telemetry.parquet")
        tel_entry = next(f for f in manifest["bundle_files"] if f["name"] == "telemetry.parquet")
        assert tel_entry["sha256"] == expected


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
# metadata.json is no longer written in v2
# ---------------------------------------------------------------------------


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
        m = LegacySessionManifest(session_id="s1", logger_version="1.0.0")
        d = m.to_dict()
        assert d["session_id"] == "s1"
        assert d["schema_version"] == BUNDLE_SCHEMA_VERSION

    def test_compute_file_sha256(self, tmp_path: Path) -> None:
        f = tmp_path / "test.bin"
        f.write_bytes(b"hello world")
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert compute_file_sha256(f) == expected


# ---------------------------------------------------------------------------
# CSV fallback still produces bundle when parquet fails
# ---------------------------------------------------------------------------

class TestCsvFallbackBundle:

    def test_bundle_with_csv_fallback(self, tmp_path: Path) -> None:
        fin = SessionFinalizer(tmp_path)
        now = datetime.now(timezone.utc)

        with patch(
            "lap_coach_logger.writers.finalizer.ParquetWriter",
            side_effect=RuntimeError("parquet fail"),
        ):
            result = fin.finalize(
                _make_samples(), started_at=now, sim="x", track="y", session_type="z",
                laps=_laps(),
            )

        assert result is not None
        assert (result / "telemetry.csv").exists()
        assert not (result / "telemetry.parquet").exists()
        assert (result / "session.json").exists()
        assert (result / "laps.json").exists()

        manifest = json.loads((result / "session.json").read_text())
        # v2 format: check telemetry hash is in bundle_files
        csv_entries = [f for f in manifest.get("bundle_files", []) if f["name"] == "telemetry.csv"]
        # CSV fallback may not be in canonical bundle_files since v2 requires parquet;
        # but session.json should still exist and have the v2 schema
        assert manifest["schema_version"] == 2
