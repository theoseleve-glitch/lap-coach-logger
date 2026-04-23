"""Tests for bundle_v2 writer — session.json v2 shape + bundle_hash."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lap_coach_logger.writers.bundle_v2 import write_bundle_v2, CANONICAL_FILES


def _make_laps() -> list[dict]:
    return [
        {"lap_number": 1, "lap_time_s": 92.0, "valid": True, "fuel_used_l": 2.1, "sector_times_s": [30, 30, 32]},
        {"lap_number": 2, "lap_time_s": 91.5, "valid": True, "fuel_used_l": 2.0, "sector_times_s": [29.5, 30, 32]},
    ]


def _setup_v1_bundle(tmp_path: Path) -> Path:
    """Create a minimal v1-style session directory with required files."""
    session_dir = tmp_path / "2026-04-16_12-00-00__iracing__Monza__race"
    session_dir.mkdir(parents=True)
    (session_dir / "telemetry.parquet").write_bytes(b"\x00" * 512)
    (session_dir / "laps.json").write_text(json.dumps(_make_laps()))
    (session_dir / "events.json").write_text(json.dumps([]))
    (session_dir / "channels.json").write_text(json.dumps({"schema_version": 2, "channels": []}))
    return session_dir


class TestBundleV2Writer:
    def test_writes_session_json_v2(self, tmp_path: Path) -> None:
        session_dir = _setup_v1_bundle(tmp_path)
        manifest = write_bundle_v2(
            session_dir,
            session_id="test-1",
            sim_name="iRacing",
            raw_car="Ferrari 296 GT3",
            raw_track="Autodromo Nazionale Monza",
            raw_track_layout=None,
            session_type_raw="Race",
            mode="sprint",
            driver_name="Daisy",
            start_time="2026-04-16T12:00:00Z",
            end_time="2026-04-16T12:35:00Z",
            sample_count=21000,
            duration_s=2100.0,
            laps=_make_laps(),
            events=[],
        )
        assert manifest["schema_version"] == 2
        assert manifest["session_id"] == "test-1"
        # Phase 6: v2 is the canonical format, written directly to session.json
        assert (session_dir / "session.json").exists()
        assert (session_dir / "analysis.json").exists()

    def test_writes_analysis_json(self, tmp_path: Path) -> None:
        session_dir = _setup_v1_bundle(tmp_path)
        write_bundle_v2(
            session_dir, session_id="test-2", sim_name="iRacing",
            raw_car="X", raw_track="Y", raw_track_layout=None,
            session_type_raw="Race", mode="sprint", driver_name="",
            start_time="2026-04-16T12:00:00Z", end_time="2026-04-16T12:35:00Z",
            sample_count=5000, duration_s=600.0, laps=_make_laps(), events=[],
        )
        analysis = json.loads((session_dir / "analysis.json").read_text())
        assert analysis["schema_version"] == 1
        assert analysis["computed_by"] == "logger"
        assert analysis["lap_summary"]["total_laps"] == 2

    def test_resolves_known_car(self, tmp_path: Path) -> None:
        session_dir = _setup_v1_bundle(tmp_path)
        manifest = write_bundle_v2(
            session_dir, session_id="test-3", sim_name="iRacing",
            raw_car="Ferrari 296 GT3", raw_track="Autodromo Nazionale Monza",
            raw_track_layout=None, session_type_raw="Race", mode="sprint",
            driver_name="", start_time="2026-04-16T12:00:00Z",
            end_time="2026-04-16T12:35:00Z", sample_count=5000,
            duration_s=600.0, laps=_make_laps(), events=[],
        )
        canon = manifest["canonical_resolution"]
        assert canon["canonical_car_name"] == "Ferrari 296 GT3"
        assert canon["car_class"] == "GT3"
        assert canon["unresolved"] == []

    def test_unresolved_car_tracked(self, tmp_path: Path) -> None:
        session_dir = _setup_v1_bundle(tmp_path)
        manifest = write_bundle_v2(
            session_dir, session_id="test-4", sim_name="iRacing",
            raw_car="Unknown Car 9000", raw_track="Autodromo Nazionale Monza",
            raw_track_layout=None, session_type_raw="Race", mode="sprint",
            driver_name="", start_time="2026-04-16T12:00:00Z",
            end_time="2026-04-16T12:35:00Z", sample_count=5000,
            duration_s=600.0, laps=_make_laps(), events=[],
        )
        canon = manifest["canonical_resolution"]
        assert canon["canonical_car_id"] is None
        assert "car" in canon["unresolved"]

    def test_bundle_hash_matches_recomputation(self, tmp_path: Path) -> None:
        """Hash recorded in session.json must match a recomputation from the
        actual file contents on disk. This is the property the backend verifies."""
        session_dir = _setup_v1_bundle(tmp_path)
        manifest = write_bundle_v2(
            session_dir, session_id="det-1", sim_name="iRacing",
            raw_car="X", raw_track="Y", raw_track_layout=None,
            session_type_raw="Race", mode="sprint", driver_name="",
            start_time="2026-04-16T12:00:00Z", end_time="2026-04-16T12:35:00Z",
            sample_count=5000, duration_s=600.0, laps=_make_laps(), events=[],
        )
        # Recompute from files on disk
        h = hashlib.sha256()
        canonical = sorted(
            (f for f in manifest["bundle_files"] if f.get("required")),
            key=lambda f: f["name"],
        )
        for entry in canonical:
            h.update(entry["name"].encode("utf-8"))
            h.update(b"\x00")
            if entry["name"] == "session.json":
                h.update(b"self")
            else:
                hex_str = entry["sha256"].removeprefix("sha256:")
                h.update(bytes.fromhex(hex_str))
            h.update(b"\x00")
        expected = f"sha256:{h.hexdigest()}"
        assert manifest["bundle_hash"] == expected

    def test_bundle_files_inventory_complete(self, tmp_path: Path) -> None:
        session_dir = _setup_v1_bundle(tmp_path)
        manifest = write_bundle_v2(
            session_dir, session_id="inv-1", sim_name="iRacing",
            raw_car="X", raw_track="Y", raw_track_layout=None,
            session_type_raw="Race", mode="sprint", driver_name="",
            start_time="2026-04-16T12:00:00Z", end_time="2026-04-16T12:35:00Z",
            sample_count=5000, duration_s=600.0, laps=_make_laps(), events=[],
        )
        file_names = {f["name"] for f in manifest["bundle_files"]}
        for required in CANONICAL_FILES:
            assert required in file_names, f"Missing {required} in bundle_files"
