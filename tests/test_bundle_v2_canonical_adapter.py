"""T040: writers expose a canonical SessionManifest→bundle_v2 adapter.

Before T040, ``SessionFinalizer`` hand-wired canonical manifest fields
(``sim_title``, ``track_layout``, ``duration_seconds``, ``total_samples``,
``started_at`` / ``ended_at``, ``session_id``) into ``write_bundle_v2``'s
legacy kwargs. This coupled two places to the legacy naming and made
it easy to drift as the shared schema evolves.

``writers.bundle_v2.write_bundle_v2_from_manifest`` is the single place
that translates the canonical manifest into the legacy wire format so
writers/* presents one consistent entry point to callers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import uuid6

from lap_schemas.v1 import SessionManifest
from lap_schemas.v1.data_quality import DataQuality
from lap_schemas.v1.environment import EnvironmentTag
from lap_schemas.v1.sensor_config import SensorConfig, SensorConfigSnapshot


def _make_manifest(started_at: datetime, ended_at: datetime) -> SessionManifest:
    return SessionManifest(
        session_id=uuid6.uuid7(),
        driver_id=uuid6.uuid7(),
        bundle_version="v2",
        capture_app="lap-coach-logger",
        capture_app_version="0.1.0",
        device_model="Desktop",
        device_os="Windows",
        device_os_version="10",
        source="iracing",
        sim_title="iRacing",
        real_hardware=None,
        car_id=uuid6.uuid7(),
        track_id=uuid6.uuid7(),
        track_layout="Grand Prix",
        environment_tag=EnvironmentTag.SIM_PRACTICE,
        objective_tag=None,
        training_block_id=None,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=(ended_at - started_at).total_seconds(),
        telemetry_checksums={},
        total_samples=5000,
        sample_rate_hz=60.0,
        data_quality=DataQuality(
            score=1.0,
            channel_completeness=1.0,
            sample_gaps_count=0,
            sample_rate_stability=1.0,
            warnings=(),
            recommendations=(),
            usable_for_overlays=True,
            usable_for_long_term_coaching=True,
        ),
        sensor_config=SensorConfigSnapshot(
            sensors=(SensorConfig(name="iRacing", sample_rate_hz=60.0),),
        ),
    )


def _seed_v1_bundle(tmp_path: Path) -> Path:
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    (session_dir / "telemetry.parquet").write_bytes(b"\x00" * 256)
    (session_dir / "laps.json").write_text("[]")
    (session_dir / "events.json").write_text("[]")
    (session_dir / "channels.json").write_text(
        '{"schema_version": 2, "channels": []}'
    )
    return session_dir


def test_write_bundle_v2_from_manifest_derives_canonical_fields(
    tmp_path: Path,
) -> None:
    from lap_coach_logger.writers.bundle_v2 import write_bundle_v2_from_manifest

    session_dir = _seed_v1_bundle(tmp_path)
    started = datetime(2026, 4, 16, 12, 0, 0, tzinfo=timezone.utc)
    ended = datetime(2026, 4, 16, 12, 35, 0, tzinfo=timezone.utc)
    manifest = _make_manifest(started, ended)

    result = write_bundle_v2_from_manifest(
        session_dir,
        manifest=manifest,
        raw_car="Ferrari 296 GT3",
        raw_track="Autodromo Nazionale Monza",
        raw_track_layout=None,
        session_type_raw="Race",
        mode="sprint",
        driver_name="Daisy",
        laps=[],
        events=[],
    )

    # Session identity + timing + sample stats derived from the manifest,
    # not re-specified by the caller.
    assert result["session_id"] == str(manifest.session_id)
    assert result["raw_source"]["sim_display_name"] == "iRacing"
    assert result["session"]["start_time"] == started.isoformat()
    assert result["session"]["end_time"] == ended.isoformat()
    assert result["session"]["duration_s"] == manifest.duration_seconds
    assert result["session"]["sample_count"] == manifest.total_samples


def test_write_bundle_v2_from_manifest_rejects_non_manifest(
    tmp_path: Path,
) -> None:
    """Guards against accidental ``dict`` passes that would silently drift."""
    import pytest

    from lap_coach_logger.writers.bundle_v2 import write_bundle_v2_from_manifest

    session_dir = _seed_v1_bundle(tmp_path)
    with pytest.raises(TypeError):
        write_bundle_v2_from_manifest(
            session_dir,
            manifest={"session_id": "not-a-manifest"},  # type: ignore[arg-type]
            raw_car="X",
            raw_track="Y",
            raw_track_layout=None,
            session_type_raw="Race",
            mode="sprint",
            driver_name="",
            laps=[],
            events=[],
        )
