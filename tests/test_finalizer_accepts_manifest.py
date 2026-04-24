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


# -- T029 --------------------------------------------------------------------

def _events() -> list:
    from lap_coach_logger.writers.bundle_schema import SessionEvent

    return [
        SessionEvent(
            event="sector",
            timestamp_utc=STARTED.isoformat(),
            detail={"sector": 1, "time_s": 32.1},
        ),
        SessionEvent(
            event="lap_complete",
            timestamp_utc=STARTED.isoformat(),
            detail={"lap_number": 1, "lap_time_s": 90.3},
        ),
        SessionEvent(
            event="flag",
            timestamp_utc=STARTED.isoformat(),
            detail={"flag": "yellow", "sector": 2},
        ),
    ]


def test_events_json_written_and_valid(tmp_path: Path) -> None:
    """T029: events.json exists and parses as a JSON list."""
    import json

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(_samples(), manifest=_manifest(), events=_events())
    assert out is not None
    events_path = out / "events.json"
    assert events_path.exists()

    data = json.loads(events_path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 3


def test_events_json_covers_sector_lap_and_flag_events(tmp_path: Path) -> None:
    """T029: each event type lands in events.json with event+timestamp."""
    import json

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(_samples(), manifest=_manifest(), events=_events())
    assert out is not None

    data = json.loads((out / "events.json").read_text(encoding="utf-8"))
    kinds = {row["event"] for row in data}
    assert {"sector", "lap_complete", "flag"}.issubset(kinds)
    for row in data:
        assert "event" in row and row["event"]
        assert "timestamp_utc" in row and row["timestamp_utc"]


def test_events_json_is_empty_list_when_no_events(tmp_path: Path) -> None:
    """T029: events list produces an empty JSON array, not absent file."""
    import json

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(_samples(), manifest=_manifest(), events=[])
    assert out is not None
    data = json.loads((out / "events.json").read_text(encoding="utf-8"))
    assert data == []


# -- T030 --------------------------------------------------------------------

def test_manifest_populates_telemetry_checksums_from_disk(tmp_path: Path) -> None:
    """T030: manifest.json lists every bundle file with its sha256 digest."""
    import hashlib
    import json

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(
        _samples(), manifest=_manifest(), laps=_laps(), events=_events()
    )
    assert out is not None

    data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    checksums = data.get("telemetry_checksums")
    assert isinstance(checksums, dict) and checksums, (
        "manifest.json must populate telemetry_checksums after finalize"
    )

    # Every listed file must exist and its sha256 must match the digest.
    for fname, digest in checksums.items():
        path = out / fname
        assert path.exists(), f"checksum entry for missing file: {fname}"
        assert isinstance(digest, str) and digest.startswith("sha256:"), (
            f"checksum for {fname} is not sha256:... format"
        )
        expected = (
            "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        )
        assert digest == expected, f"checksum mismatch for {fname}"


def test_manifest_checksums_cover_core_bundle_files(tmp_path: Path) -> None:
    """T030: the core bundle files (telemetry, laps, events) are all listed."""
    import json

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(
        _samples(), manifest=_manifest(), laps=_laps(), events=_events()
    )
    assert out is not None

    data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    checksums = data["telemetry_checksums"]
    expected_files = {
        "telemetry.parquet",
        "laps.parquet",
        "laps.json",
        "events.json",
    }
    missing = expected_files - set(checksums.keys())
    assert not missing, f"manifest.json missing checksums for: {missing}"


def test_manifest_checksum_matches_on_re_read(tmp_path: Path) -> None:
    """T030 (re-read contract): validate + verify checksums round-trip."""
    import hashlib
    import json

    from lap_schemas.v1 import SessionManifest

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(_samples(), manifest=_manifest(), laps=_laps())
    assert out is not None

    data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    # SessionManifest.model_validate proves the shape is still valid after
    # the finalizer updates telemetry_checksums.
    parsed = SessionManifest.model_validate(data)
    assert parsed.telemetry_checksums

    for fname, digest in parsed.telemetry_checksums.items():
        path = out / fname
        assert digest == (
            "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        )


# -- T031 --------------------------------------------------------------------

def _list_dirs(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def test_atomic_rename_removes_temp_prefix_on_success(tmp_path: Path) -> None:
    """T031: after successful finalize, no ``_tmp_`` directory lingers."""
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(_samples(), manifest=_manifest(), laps=_laps())
    assert out is not None

    # Final bundle dir exists; no sibling _tmp_ scaffold remains.
    assert out.is_dir()
    temps = [name for name in _list_dirs(tmp_path) if name.startswith("_tmp_")]
    assert temps == [], f"stale _tmp_ dirs after finalize: {temps}"


def test_finalize_failure_leaves_no_final_dir_only_tmp(tmp_path: Path) -> None:
    """T031: a mid-write exception must leave the FINAL name absent.

    Partial bundles are allowed to linger under ``_tmp_`` for later
    cleanup (``cleanup_stale_temps``), but the final folder name MUST
    NOT appear — consumers pick up only complete bundles.
    """
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())

    # Force a late-stage write to raise by replacing the instance method.
    def _explode(*_a, **_kw):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated late-stage writer failure")

    fin._write_events = _explode  # type: ignore[method-assign]

    out = fin.finalize(_samples(), manifest=_manifest(), laps=_laps())
    assert out is None, "finalize must return None on failure"

    # No final bundle dir — consumers see nothing.
    dirs = _list_dirs(tmp_path)
    final_candidates = [d for d in dirs if not d.startswith("_tmp_")]
    assert final_candidates == [], (
        f"final dir appeared despite mid-write failure: {final_candidates}"
    )


def test_cleanup_stale_temps_removes_orphan_tmp_dirs(tmp_path: Path) -> None:
    """T031: ``cleanup_stale_temps`` sweeps any orphaned ``_tmp_`` scaffolds."""
    # Simulate an orphan from a prior crashed run.
    orphan = tmp_path / "_tmp_2026-04-24_10-00-00__iracing__sebring__unknown"
    orphan.mkdir()
    (orphan / "partial.json").write_text("{}", encoding="utf-8")

    cleaned = SessionFinalizer.cleanup_stale_temps(tmp_path)
    assert cleaned >= 1
    assert not orphan.exists()


# -- T032 --------------------------------------------------------------------

def _manifest_with_sensors(*sensors: SensorConfig) -> SessionManifest:
    m = _manifest()
    return m.model_copy(
        update={
            "sensor_config": SensorConfigSnapshot(
                sensors=tuple(sensors),
                hardware_id="desktop-rig-01",
                firmware_version="2.0.0",
            )
        }
    )


def test_manifest_sensor_config_persists_to_disk(tmp_path: Path) -> None:
    """T032: sensor_config (sensors + adapter info) persists via manifest.json."""
    import json

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    manifest = _manifest_with_sensors(
        SensorConfig(name="irsdk", sample_rate_hz=60.0, enabled=True),
        SensorConfig(name="racebox_gnss", sample_rate_hz=25.0, enabled=False),
    )
    out = fin.finalize(_samples(), manifest=manifest)
    assert out is not None

    data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    sc = data.get("sensor_config")
    assert isinstance(sc, dict) and sc, "manifest.json must include sensor_config"
    assert sc.get("hardware_id") == "desktop-rig-01"
    assert sc.get("firmware_version") == "2.0.0"


def test_sensor_config_round_trips_via_pydantic_model(tmp_path: Path) -> None:
    """T032: re-reading manifest.json reconstructs the exact SensorConfigSnapshot."""
    import json

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    manifest = _manifest_with_sensors(
        SensorConfig(name="irsdk", sample_rate_hz=60.0),
    )
    out = fin.finalize(_samples(), manifest=manifest)
    assert out is not None

    data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    parsed = SessionManifest.model_validate(data)
    assert parsed.sensor_config == manifest.sensor_config


def test_sensor_config_sensors_list_populated_and_nonempty(tmp_path: Path) -> None:
    """T032: sensors tuple carries at least one entry with adapter + rate."""
    import json

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(_samples(), manifest=_manifest())
    assert out is not None

    data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    sensors = data["sensor_config"]["sensors"]
    assert isinstance(sensors, list) and sensors, "sensors must be populated"
    first = sensors[0]
    assert first["name"]  # adapter name set
    assert first["sample_rate_hz"] > 0  # rate is positive-only per schema


# -- T033 --------------------------------------------------------------------

def _rich_data_quality() -> DataQuality:
    return DataQuality(
        score=88.5,
        gps_fix_quality=4.0,
        gps_satellite_count_avg=11,
        channel_completeness=97.25,
        sample_gaps_count=3,
        sample_rate_stability=0.02,
        warnings=("sample_gap_at_lap_2",),
        recommendations=("check_gps_antenna",),
        usable_for_overlays=True,
        usable_for_long_term_coaching=False,
    )


def _manifest_with_quality(dq: DataQuality) -> SessionManifest:
    return _manifest().model_copy(update={"data_quality": dq})


def test_data_quality_all_submetrics_persist(tmp_path: Path) -> None:
    """T033: every DataQuality sub-metric survives the manifest round-trip."""
    import json

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    dq = _rich_data_quality()
    out = fin.finalize(_samples(), manifest=_manifest_with_quality(dq))
    assert out is not None

    data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    written = data.get("data_quality")
    assert isinstance(written, dict) and written

    for key in (
        "score",
        "gps_fix_quality",
        "gps_satellite_count_avg",
        "channel_completeness",
        "sample_gaps_count",
        "sample_rate_stability",
        "warnings",
        "recommendations",
        "usable_for_overlays",
        "usable_for_long_term_coaching",
    ):
        assert key in written, f"data_quality.{key} missing from manifest.json"


def test_data_quality_round_trips_via_pydantic_model(tmp_path: Path) -> None:
    """T033: DataQuality reconstructs byte-for-byte via model_validate."""
    import json

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    dq = _rich_data_quality()
    out = fin.finalize(_samples(), manifest=_manifest_with_quality(dq))
    assert out is not None

    data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    parsed = SessionManifest.model_validate(data)
    assert parsed.data_quality == dq


def test_data_quality_score_within_schema_bounds(tmp_path: Path) -> None:
    """T033: score respects 0-100 constraint; warnings/recommendations stay tuples."""
    import json

    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    dq = _rich_data_quality()
    out = fin.finalize(_samples(), manifest=_manifest_with_quality(dq))
    assert out is not None

    data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    written = data["data_quality"]
    assert 0 <= written["score"] <= 100
    assert 0 <= written["channel_completeness"] <= 100
    assert isinstance(written["warnings"], list) and written["warnings"]
    assert isinstance(written["recommendations"], list) and written["recommendations"]
