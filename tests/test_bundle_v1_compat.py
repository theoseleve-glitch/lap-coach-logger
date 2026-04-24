"""T038: v1→v2 bundle compat shim — read old bundles, re-serialize as v2.

The reprocess path reads a legacy v1 bundle directory (session.json
with the flat legacy shape + telemetry.csv / laps.json / events.json)
and produces a ``lap_schemas.v1.SessionManifest`` the current
finalizer / upload pipeline can consume. UUID-typed fields the v1
bundle doesn't carry (driver_id, car_id, track_id) are minted fresh
so downstream validation doesn't reject the reprocessed session.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lap_coach_logger.writers.bundle_v1_compat import (
    load_v1_bundle_as_manifest,
)
from lap_schemas.v1 import SessionManifest


def _write_legacy_bundle(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    session_json = {
        "session_id": "legacy-session-0001",
        "schema_version": "1.0.0",
        "telemetry_schema_version": "2.0.0",
        "logger_version": "1.1.0",
        "adapter": "iRacingAdapter",
        "sim_name": "iracing",
        "started_at_utc": "2026-04-20T14:30:00+00:00",
        "ended_at_utc": "2026-04-20T15:00:00+00:00",
        "timezone_offset": "+00:00",
        "session_type": "practice",
        "track_name": "sebring",
        "car_name": "ferrari-296-gt3",
        "sample_count": 900,
        "sample_rate_hz": 30.0,
    }
    (folder / "session.json").write_text(
        json.dumps(session_json, indent=2), encoding="utf-8"
    )
    # Minimal companion files so telemetry-checksum path has something to hash.
    (folder / "telemetry.csv").write_text("col1,col2\n1,2\n", encoding="utf-8")
    (folder / "laps.json").write_text("[]", encoding="utf-8")
    return folder


def test_shim_returns_valid_v2_session_manifest(tmp_path: Path) -> None:
    bundle = _write_legacy_bundle(tmp_path / "legacy-bundle")
    manifest = load_v1_bundle_as_manifest(bundle)
    assert isinstance(manifest, SessionManifest)
    assert manifest.bundle_version == "v2"


def test_shim_preserves_session_timing_from_legacy_session_json(
    tmp_path: Path,
) -> None:
    bundle = _write_legacy_bundle(tmp_path / "legacy-bundle")
    manifest = load_v1_bundle_as_manifest(bundle)

    assert manifest.started_at == datetime(
        2026, 4, 20, 14, 30, 0, tzinfo=timezone.utc
    )
    assert manifest.ended_at == datetime(
        2026, 4, 20, 15, 0, 0, tzinfo=timezone.utc
    )
    assert manifest.duration_seconds == pytest.approx(1800.0)


def test_shim_preserves_sim_and_track_metadata(tmp_path: Path) -> None:
    bundle = _write_legacy_bundle(tmp_path / "legacy-bundle")
    manifest = load_v1_bundle_as_manifest(bundle)

    assert manifest.sim_title == "iracing"
    assert manifest.track_layout == "sebring"
    # ``source`` enum-ish string — shim picks a reasonable default from sim.
    assert manifest.source == "iracing"


def test_shim_mints_fresh_uuid7s_for_missing_identity_fields(
    tmp_path: Path,
) -> None:
    bundle = _write_legacy_bundle(tmp_path / "legacy-bundle")
    manifest = load_v1_bundle_as_manifest(bundle)
    # v1 didn't carry UUID7s; the shim generates them so v2 validation passes.
    for uid in (manifest.session_id, manifest.driver_id, manifest.car_id, manifest.track_id):
        assert uid.version == 7


def test_shim_roundtrips_through_pydantic_model(tmp_path: Path) -> None:
    """Reprocess path: shim→dump→reload must produce an equal manifest."""
    bundle = _write_legacy_bundle(tmp_path / "legacy-bundle")
    manifest = load_v1_bundle_as_manifest(bundle)

    dumped = manifest.model_dump_json()
    reloaded = SessionManifest.model_validate_json(dumped)
    assert reloaded == manifest


def test_shim_rejects_bundle_without_session_json(tmp_path: Path) -> None:
    (tmp_path / "empty-bundle").mkdir()
    with pytest.raises(FileNotFoundError):
        load_v1_bundle_as_manifest(tmp_path / "empty-bundle")
