"""Unit tests for bundle_validator — no DB needed, fast."""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest

from app.bundle_validator import (
    REQUIRED_FILES,
    ValidationError,
    ValidatedBundle,
    validate_bundle,
)


# ---------------------------------------------------------------------------
# Helpers — build a minimal valid v2 bundle in-memory
# ---------------------------------------------------------------------------

def _make_analysis() -> dict:
    return {
        "schema_version": 1,
        "computed_at": "2026-04-16T12:00:00Z",
        "computed_by": "logger",
        "session_quality": {"overall_score": 0.9},
        "lap_summary": {"total_laps": 5, "valid_laps": 5},
        "recommendation": {"verdict": "ready_for_review"},
    }


def _make_manifest(
    session_id: str = "test-session-1",
    sim_id: str = "iracing",
    bundle_files: list | None = None,
    bundle_hash: str | None = None,
    schema_version: int = 2,
) -> dict:
    return {
        "schema_version": schema_version,
        "logger_version": "0.5.2",
        "bundle_hash": bundle_hash or "sha256:placeholder",
        "session_id": session_id,
        "raw_source": {
            "sim_id": sim_id,
            "raw_car": "Ferrari 296 GT3",
            "raw_track": "Monza",
            "raw_track_layout": None,
            "session_type_raw": "Race",
            "captured_at": "2026-04-16T12:00:00Z",
        },
        "canonical_resolution": {
            "lut_version": "2026-04-16",
            "canonical_car_id": str(uuid.uuid4()),
            "canonical_car_name": "Ferrari 296 GT3",
            "car_class": "GT3",
            "canonical_track_id": str(uuid.uuid4()),
            "canonical_track_name": "Monza",
            "canonical_track_layout": "GP",
            "unresolved": [],
        },
        "session": {
            "session_uid": session_id,
            "mode": "sprint",
            "driver_name": "Daisy",
            "start_time": "2026-04-16T12:00:00Z",
            "end_time": "2026-04-16T12:35:00Z",
            "sample_count": 21000,
            "lap_count": 5,
        },
        "analysis_readiness": {
            "ready_for_analysis": True,
            "blockers": [],
        },
        "bundle_files": bundle_files or [],
    }


def _build_valid_parts() -> tuple[dict[str, bytes], str]:
    """Build a complete valid bundle and return (parts, idempotency_key)."""
    analysis = json.dumps(_make_analysis()).encode()
    laps = json.dumps([
        {"lap_number": i, "lap_time_s": 92.0 + i, "valid": True, "fuel_used_l": 2.1, "sector_times_s": []}
        for i in range(1, 6)
    ]).encode()
    events = json.dumps([]).encode()
    channels = json.dumps({"schema_version": 2, "channels": []}).encode()
    telemetry = b"\x00" * 1024  # placeholder parquet bytes

    # Compute hashes
    file_hashes = {
        "analysis.json": "sha256:" + hashlib.sha256(analysis).hexdigest(),
        "telemetry.parquet": "sha256:" + hashlib.sha256(telemetry).hexdigest(),
        "laps.json": "sha256:" + hashlib.sha256(laps).hexdigest(),
        "events.json": "sha256:" + hashlib.sha256(events).hexdigest(),
        "channels.json": "sha256:" + hashlib.sha256(channels).hexdigest(),
    }

    bundle_files = [
        {"name": "session.json", "sha256": "self", "size_bytes": 0, "required": True},
        {"name": "analysis.json", "sha256": file_hashes["analysis.json"], "size_bytes": len(analysis), "required": True},
        {"name": "telemetry.parquet", "sha256": file_hashes["telemetry.parquet"], "size_bytes": len(telemetry), "required": True},
        {"name": "laps.json", "sha256": file_hashes["laps.json"], "size_bytes": len(laps), "required": True},
        {"name": "events.json", "sha256": file_hashes["events.json"], "size_bytes": len(events), "required": True},
        {"name": "channels.json", "sha256": file_hashes["channels.json"], "size_bytes": len(channels), "required": True},
    ]

    # Compute bundle_hash
    h = hashlib.sha256()
    for entry in sorted(bundle_files, key=lambda f: f["name"]):
        h.update(entry["name"].encode("utf-8"))
        h.update(b"\x00")
        if entry["name"] == "session.json":
            h.update(b"self")
        else:
            hex_str = entry["sha256"].removeprefix("sha256:")
            try:
                h.update(bytes.fromhex(hex_str))
            except ValueError:
                h.update(hex_str.encode("utf-8"))
        h.update(b"\x00")
    bundle_hash_hex = h.hexdigest()
    bundle_hash_str = "sha256:" + bundle_hash_hex

    manifest = _make_manifest(bundle_files=bundle_files, bundle_hash=bundle_hash_str)
    session_json = json.dumps(manifest).encode()

    # Update session.json hash in bundle_files after serialisation
    actual_session_hash = "sha256:" + hashlib.sha256(session_json).hexdigest()
    manifest["bundle_files"][0]["sha256"] = "self"  # stays self
    manifest["bundle_files"][0]["size_bytes"] = len(session_json)

    # Re-serialize (hash is self-referential)
    session_json = json.dumps(manifest).encode()

    idempotency_key = str(uuid.UUID(bundle_hash_hex[:32]))

    parts = {
        "session.json": session_json,
        "analysis.json": analysis,
        "telemetry.parquet": telemetry,
        "laps.json": laps,
        "events.json": events,
        "channels.json": channels,
    }

    return parts, idempotency_key


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidBundle:
    def test_accepts_minimal_valid_bundle(self) -> None:
        parts, idem = _build_valid_parts()
        result = validate_bundle(parts, idem)
        assert isinstance(result, ValidatedBundle)
        assert result.session_id == "test-session-1"
        assert result.sim_id == "iracing"
        assert len(result.laps) == 5

    def test_extracts_canonical_fields(self) -> None:
        parts, idem = _build_valid_parts()
        result = validate_bundle(parts, idem)
        assert isinstance(result, ValidatedBundle)
        assert result.canonical_car_id is not None
        assert result.car_class == "GT3"
        assert result.mode == "sprint"


class TestMissingFiles:
    def test_rejects_missing_session_json(self) -> None:
        parts, idem = _build_valid_parts()
        del parts["session.json"]
        result = validate_bundle(parts, idem)
        assert isinstance(result, ValidationError)
        assert result.code == "missing_required_file"

    def test_rejects_missing_telemetry(self) -> None:
        parts, idem = _build_valid_parts()
        del parts["telemetry.parquet"]
        result = validate_bundle(parts, idem)
        assert isinstance(result, ValidationError)
        # Either missing_required_file or inventory_mismatch — both valid
        assert result.code in ("missing_required_file", "inventory_mismatch")


class TestSchemaValidation:
    def test_rejects_wrong_schema_version(self) -> None:
        parts, idem = _build_valid_parts()
        manifest = json.loads(parts["session.json"])
        manifest["schema_version"] = 1
        parts["session.json"] = json.dumps(manifest).encode()
        result = validate_bundle(parts, idem)
        assert isinstance(result, ValidationError)
        assert result.code == "unsupported_schema_version"

    def test_rejects_unknown_sim_id(self) -> None:
        parts, idem = _build_valid_parts()
        manifest = json.loads(parts["session.json"])
        manifest["raw_source"]["sim_id"] = "rfactor2"
        parts["session.json"] = json.dumps(manifest).encode()
        result = validate_bundle(parts, idem)
        assert isinstance(result, ValidationError)
        assert result.code == "unknown_sim_id"

    def test_rejects_invalid_mode(self) -> None:
        parts, idem = _build_valid_parts()
        manifest = json.loads(parts["session.json"])
        manifest["session"]["mode"] = "drift"
        parts["session.json"] = json.dumps(manifest).encode()
        result = validate_bundle(parts, idem)
        assert isinstance(result, ValidationError)
        assert result.code == "invalid_schema"


class TestHashVerification:
    def test_rejects_tampered_laps_hash(self) -> None:
        parts, idem = _build_valid_parts()
        parts["laps.json"] = b"[{\"tampered\": true}]"
        result = validate_bundle(parts, idem)
        assert isinstance(result, ValidationError)
        assert result.code == "file_hash_mismatch"

    def test_rejects_idempotency_key_mismatch(self) -> None:
        parts, _ = _build_valid_parts()
        result = validate_bundle(parts, str(uuid.uuid4()))
        assert isinstance(result, ValidationError)
        assert result.code == "bundle_hash_mismatch"


class TestSizeEnforcement:
    def test_rejects_oversized_bundle(self) -> None:
        parts, idem = _build_valid_parts()
        result = validate_bundle(parts, idem, max_total_bytes=100)
        assert isinstance(result, ValidationError)
        assert result.code == "bundle_too_large"


class TestInventoryMismatch:
    def test_rejects_extra_uploaded_file(self) -> None:
        parts, idem = _build_valid_parts()
        parts["unknown_file.dat"] = b"extra"
        result = validate_bundle(parts, idem)
        assert isinstance(result, ValidationError)
        assert result.code == "inventory_mismatch"


class TestConsistency:
    def test_rejects_mismatched_session_uid(self) -> None:
        parts, idem = _build_valid_parts()
        manifest = json.loads(parts["session.json"])
        manifest["session"]["session_uid"] = "different-uid"
        parts["session.json"] = json.dumps(manifest).encode()
        result = validate_bundle(parts, idem)
        assert isinstance(result, ValidationError)
        assert result.code == "inconsistent_bundle"
