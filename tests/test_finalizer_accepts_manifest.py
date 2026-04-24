"""Tests for SessionFinalizer.finalize(manifest=...) (sprint T025).

Step 1 of the T025-T034 finalizer rewrite: the finalize entry point
must accept a shared ``lap_schemas.v1.SessionManifest`` and derive
session identity / timing / sim+track metadata from it instead of the
ad-hoc kwarg shower. Later steps will flip the rest of the pipeline
(bundle v2 layout, atomic writes, checksums, etc.) onto the same
contract.

Existing callers still pass individual kwargs; those tests stay green.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import uuid6

from lap_coach_logger.config.models import QualityConfig
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.writers.finalizer import SessionFinalizer
from lap_schemas.v1 import SessionManifest
from lap_schemas.v1.data_quality import DataQuality
from lap_schemas.v1.environment import EnvironmentTag
from lap_schemas.v1.sensor_config import SensorConfig, SensorConfigSnapshot


STARTED = datetime(2026, 4, 24, 10, 0, 0, tzinfo=timezone.utc)
ENDED = datetime(2026, 4, 24, 10, 30, 0, tzinfo=timezone.utc)


def _minimal_quality() -> DataQuality:
    return DataQuality(
        score=95.0,
        channel_completeness=100.0,
        sample_gaps_count=0,
        sample_rate_stability=0.0,
        usable_for_overlays=True,
        usable_for_long_term_coaching=True,
    )


def _manifest(
    *,
    session_id: str | None = None,
    sim_title: str = "iracing",
    track_layout: str = "sebring-full",
) -> SessionManifest:
    return SessionManifest(
        session_id=uuid6.UUID(session_id) if session_id else uuid6.uuid7(),
        driver_id=uuid6.uuid7(),
        bundle_version="v2",
        capture_app="lap-coach-logger",
        capture_app_version="2.0.0",
        device_model="Desktop",
        device_os="Windows",
        device_os_version="11",
        source="iracing",
        sim_title=sim_title,
        real_hardware=None,
        car_id=uuid6.uuid7(),
        track_id=uuid6.uuid7(),
        track_layout=track_layout,
        environment_tag=EnvironmentTag.SIM_PRACTICE,
        objective_tag=None,
        training_block_id=None,
        started_at=STARTED,
        ended_at=ENDED,
        duration_seconds=(ENDED - STARTED).total_seconds(),
        telemetry_checksums={},
        total_samples=60,
        sample_rate_hz=60.0,
        data_quality=_minimal_quality(),
        sensor_config=SensorConfigSnapshot(
            sensors=(SensorConfig(name="irsdk", sample_rate_hz=60.0),),
        ),
    )


def _samples(n: int = 60) -> list[TelemetrySample]:
    return [
        TelemetrySample(
            sim="iracing",
            session_uid="ignored-by-manifest-path",
            session_time_s=float(i),
            lap_number=1,
            lap_dist_pct=i / n,
            speed_kph=120.0,
        )
        for i in range(n)
    ]


def test_finalize_accepts_manifest_kwarg(tmp_path: Path) -> None:
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    manifest = _manifest()

    # Should accept the kwarg without raising and produce a bundle.
    out = fin.finalize(_samples(), manifest=manifest)

    assert out is not None, "finalize(manifest=...) must produce a bundle"
    assert out.exists() and out.is_dir()


def test_manifest_overrides_session_identity_and_timing(tmp_path: Path) -> None:
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    session_id_hex = "019dc062-29f9-71fd-b4b3-882c4401eaa1"
    manifest = _manifest(
        session_id=session_id_hex, sim_title="iracing", track_layout="sebring-full"
    )

    out = fin.finalize(
        _samples(),
        manifest=manifest,
        # These must be overridden by the manifest values above.
        session_uid="should-be-overridden",
        sim="should-be-overridden",
        track="should-be-overridden",
        started_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        ended_at=datetime(2020, 1, 1, 0, 1, tzinfo=timezone.utc),
    )
    assert out is not None

    import json

    session_json = json.loads((out / "session.json").read_text(encoding="utf-8"))
    # session_id derived from manifest, not the overridden kwarg.
    assert session_json["session_id"] == session_id_hex
    # Started-at timestamp comes from the manifest (2026, not 2020).
    assert STARTED.isoformat() in json.dumps(session_json)
    # Folder name reflects manifest sim, not the override.
    assert "iracing" in out.name


def test_finalize_without_manifest_keeps_backward_compat(tmp_path: Path) -> None:
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())

    # Old-style kwargs path must remain green.
    out = fin.finalize(
        _samples(),
        started_at=STARTED,
        ended_at=ENDED,
        sim="iracing",
        track="Nurburgring",
        session_uid="legacy-uid-42",
    )
    assert out is not None


def test_finalize_manifest_requires_sessionmanifest_instance(tmp_path: Path) -> None:
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    with pytest.raises((TypeError, ValueError)):
        fin.finalize(
            _samples(), manifest={"session_id": "bogus"}  # type: ignore[arg-type]
        )


def test_manifest_written_in_bundle_v2_format(tmp_path: Path) -> None:
    """T026: when manifest is supplied, bundle contains manifest.json (v2)."""
    import json

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    manifest = _manifest()
    out = fin.finalize(_samples(), manifest=manifest)
    assert out is not None

    manifest_path = out / "manifest.json"
    assert manifest_path.exists(), "Bundle v2 must contain manifest.json"

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Round-trip through the shared Pydantic model to prove the shape.
    parsed = SessionManifest.model_validate(data)
    assert parsed.session_id == manifest.session_id
    assert parsed.bundle_version == "v2"
    assert parsed.sim_title == "iracing"
    assert parsed.track_layout == "sebring-full"


def test_bundle_v2_manifest_persists_core_identity(tmp_path: Path) -> None:
    """Manifest JSON must retain driver/car/track UUIDs for ingest joins."""
    import json

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    manifest = _manifest()
    out = fin.finalize(_samples(), manifest=manifest)
    assert out is not None

    data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert data["session_id"] == str(manifest.session_id)
    assert data["driver_id"] == str(manifest.driver_id)
    assert data["car_id"] == str(manifest.car_id)
    assert data["track_id"] == str(manifest.track_id)


def test_manifest_json_absent_on_legacy_kwarg_path(tmp_path: Path) -> None:
    """Legacy ad-hoc-kwarg finalize path must NOT emit v2 manifest.json."""
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(
        _samples(),
        started_at=STARTED,
        ended_at=ENDED,
        sim="iracing",
        track="nordschleife",
        session_uid="legacy-uid",
    )
    assert out is not None
    assert not (out / "manifest.json").exists(), (
        "legacy path must not emit v2 manifest.json (keeps old consumers quiet)"
    )


def test_finalize_writes_telemetry_parquet_by_default(tmp_path: Path) -> None:
    """T027: pyarrow-backed parquet is the primary telemetry output."""
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(_samples(), manifest=_manifest())
    assert out is not None
    assert (out / "telemetry.parquet").exists(), (
        "expected telemetry.parquet as primary output (pyarrow)"
    )
    assert (out / "telemetry.parquet").stat().st_size > 0


def test_finalize_falls_back_to_csv_when_parquet_fails(
    tmp_path: Path, monkeypatch
) -> None:
    """T027: CSV fallback engages when parquet writing raises."""
    from lap_coach_logger.writers import finalizer as finalizer_mod

    class _BrokenParquetWriter:
        def __init__(self, *_a, **_kw) -> None:
            pass

        def open(self, *_a, **_kw) -> None:
            raise RuntimeError("simulated parquet failure")

        def write_samples(self, *_a, **_kw) -> None:
            raise RuntimeError("unreachable")

        def close(self) -> None:
            pass

    monkeypatch.setattr(finalizer_mod, "ParquetWriter", _BrokenParquetWriter)

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(_samples(), manifest=_manifest())
    assert out is not None
    # Parquet should be absent, CSV fallback should be present.
    assert not (out / "telemetry.parquet").exists()
    assert (out / "telemetry.csv").exists(), (
        "CSV fallback must engage when parquet writing fails"
    )
    assert (out / "telemetry.csv").stat().st_size > 0


def test_finalize_telemetry_file_is_non_empty_and_contains_samples(
    tmp_path: Path,
) -> None:
    """T027: emitted telemetry file has a row per sample (smoke-level)."""
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(_samples(n=40), manifest=_manifest())
    assert out is not None
    telemetry = out / "telemetry.parquet"
    assert telemetry.exists()
    # A parquet file with 40 rows should be at least 1KB — smoke floor.
    assert telemetry.stat().st_size > 500


# -- T028 --------------------------------------------------------------------

def _laps(n: int = 3) -> list:
    from lap_coach_logger.writers.bundle_schema import LegacyLapRecord

    return [
        LegacyLapRecord(
            lap_number=i + 1,
            start_session_time_s=float(i) * 90.0,
            end_session_time_s=float(i + 1) * 90.0,
            lap_time_s=90.0 + i * 0.5,
            classification="clean" if i % 2 == 0 else "in_lap",
            sample_count=1200,
            max_speed_kph=200.0 + i,
        )
        for i in range(n)
    ]


def test_finalize_writes_laps_parquet_with_manifest(tmp_path: Path) -> None:
    """T028: manifest path emits laps.parquet alongside laps.json."""
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(_samples(), manifest=_manifest(), laps=_laps())
    assert out is not None
    assert (out / "laps.parquet").exists(), "expected laps.parquet in v2 bundle"
    assert (out / "laps.parquet").stat().st_size > 0


def test_laps_parquet_round_trips_to_lap_record_shape(tmp_path: Path) -> None:
    """T028: laps.parquet rows round-trip back to the LegacyLapRecord shape."""
    from lap_coach_logger.writers.bundle_schema import LegacyLapRecord

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    laps = _laps(3)
    out = fin.finalize(_samples(), manifest=_manifest(), laps=laps)
    assert out is not None

    import pyarrow.parquet as pq

    table = pq.read_table(out / "laps.parquet")
    rows = table.to_pylist()
    assert len(rows) == len(laps)

    for original, row in zip(laps, rows):
        # Reconstruct the record from the parquet row; all fields must match.
        reconstructed = LegacyLapRecord(**row)
        assert reconstructed == original


def test_laps_parquet_absent_when_no_laps_supplied(tmp_path: Path) -> None:
    """No laps → no laps.parquet (avoid empty-file noise)."""
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(_samples(), manifest=_manifest(), laps=[])
    assert out is not None
    assert not (out / "laps.parquet").exists()


def test_laps_parquet_not_written_on_legacy_path(tmp_path: Path) -> None:
    """Legacy kwarg path skips v2 laps.parquet for backward compat."""
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(
        _samples(),
        started_at=STARTED,
        ended_at=ENDED,
        sim="iracing",
        track="spa",
        laps=_laps(),
    )
    assert out is not None
    assert not (out / "laps.parquet").exists()
