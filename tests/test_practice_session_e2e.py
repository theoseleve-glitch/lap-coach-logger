"""T201: Integration test — full Practice session from
sim-start → finalize.

End-to-end exercise of the recording pipeline using the v2
manifest path:

1. Build a SessionManifest with ``EnvironmentTag.SIM_PRACTICE``
   (the v2 schema's representation of a Practice session).
2. Generate synthetic telemetry samples + lap records spanning
   multiple laps.
3. Finalize via the real :class:`SessionFinalizer` with the
   manifest path (T026-T030 plumbing).
4. Assert the resulting Bundle v2 directory has all required
   files: ``manifest.json``, ``telemetry.parquet``,
   ``laps.parquet``.
5. Assert the manifest carries the SIM_PRACTICE tag.
6. Assert atomic write: no leftover ``.tmp`` directories.

T031 pinned the atomic-write contract; T026-T030 pinned each
individual writer; T201 is the cross-cutting integration that
proves the *whole sim-start-to-finalize flow* lands a valid
Bundle v2 on disk for the most common session type.

No mocks — real production code paths, real disk writes.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import uuid6

from lap_coach_logger.config.models import QualityConfig
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.writers.bundle_schema import LegacyLapRecord
from lap_coach_logger.writers.finalizer import SessionFinalizer
from lap_schemas.v1 import SessionManifest
from lap_schemas.v1.data_quality import DataQuality
from lap_schemas.v1.environment import EnvironmentTag
from lap_schemas.v1.sensor_config import SensorConfig, SensorConfigSnapshot


_PRACTICE_LAPS = 5
_SAMPLES_PER_LAP = 60  # 1 lap = 60 samples at 1 Hz = 60s lap time
_PRACTICE_SAMPLES = _PRACTICE_LAPS * _SAMPLES_PER_LAP

_STARTED = datetime(2026, 4, 24, 10, 0, 0, tzinfo=timezone.utc)
_ENDED = _STARTED + timedelta(seconds=_PRACTICE_SAMPLES)


# -- fixtures ---------------------------------------------------------


def _practice_manifest(
    *,
    session_id: str | None = None,
    sim_title: str = "iracing",
    track_layout: str = "spa-grand-prix",
) -> SessionManifest:
    """Build a SessionManifest tagged for a Practice session
    (``EnvironmentTag.SIM_PRACTICE`` is the v2 schema's
    representation of session_type=Practice)."""
    return SessionManifest(
        session_id=(
            uuid6.UUID(session_id) if session_id else uuid6.uuid7()
        ),
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
        started_at=_STARTED,
        ended_at=_ENDED,
        duration_seconds=(_ENDED - _STARTED).total_seconds(),
        telemetry_checksums={},
        total_samples=_PRACTICE_SAMPLES,
        sample_rate_hz=1.0,
        data_quality=DataQuality(
            score=95.0,
            channel_completeness=100.0,
            sample_gaps_count=0,
            sample_rate_stability=0.0,
            usable_for_overlays=True,
            usable_for_long_term_coaching=True,
        ),
        sensor_config=SensorConfigSnapshot(
            sensors=(SensorConfig(name="irsdk", sample_rate_hz=60.0),),
        ),
    )


def _practice_samples() -> list[TelemetrySample]:
    """Synthetic Practice session: 5 laps × 60 samples each.
    Samples carry realistic-ish channel values so quality
    gates pass."""
    out: list[TelemetrySample] = []
    for global_idx in range(_PRACTICE_SAMPLES):
        lap_num = 1 + (global_idx // _SAMPLES_PER_LAP)
        idx_in_lap = global_idx % _SAMPLES_PER_LAP
        out.append(
            TelemetrySample(
                timestamp_utc=(
                    _STARTED + timedelta(seconds=global_idx)
                ).isoformat(),
                sim="iracing",
                session_uid="practice-e2e",
                session_time_s=float(global_idx),
                lap_number=lap_num,
                lap_distance_m=float(idx_in_lap * 100),
                lap_dist_pct=idx_in_lap / _SAMPLES_PER_LAP,
                speed_kph=140.0 + float(global_idx % 10),
                throttle_pct=0.55 + float(global_idx % 5) * 0.05,
                brake_pct=0.05 if global_idx % 12 == 0 else 0.0,
                steering_deg=float((-3 + (global_idx % 7)) * 1.2),
                gear=3 + (global_idx % 3),
                rpm=5400.0 + float(global_idx % 400),
                world_pos_x=float(global_idx),
                world_pos_y=0.0,
                world_pos_z=float(idx_in_lap),
                yaw_deg=float(global_idx % 360),
                long_accel_g=0.15,
                lat_accel_g=0.18,
                is_on_track=True,
                is_in_pits=False,
                track_name="Spa",
                car_name="GT3",
                session_type="Practice",
            )
        )
    return out


def _practice_lap_records() -> list[LegacyLapRecord]:
    """One LegacyLapRecord per Practice lap with realistic
    timings."""
    records: list[LegacyLapRecord] = []
    for lap_num in range(1, _PRACTICE_LAPS + 1):
        start_s = float((lap_num - 1) * _SAMPLES_PER_LAP)
        end_s = float(lap_num * _SAMPLES_PER_LAP)
        records.append(LegacyLapRecord(
            lap_number=lap_num,
            start_session_time_s=start_s,
            end_session_time_s=end_s,
            lap_time_s=end_s - start_s,
            out_lap=(lap_num == 1),
            in_lap=False,
            invalid=False,
            classification="clean",
            has_complete_telemetry=True,
            valid_for_analysis=True,
            lap_time_valid=True,
            likely_flying_lap=(lap_num != 1),
            clean_lap=(lap_num != 1),
            sample_count=_SAMPLES_PER_LAP,
            max_speed_kph=180.0 + float(lap_num),
        ))
    return records


def _finalize_practice(tmp_path: Path) -> Path:
    """Run a complete Practice finalize. Returns the bundle
    directory."""
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(
        _practice_samples(),
        manifest=_practice_manifest(),
        laps=_practice_lap_records(),
    )
    assert out is not None, (
        "finalize(manifest=...) must produce a bundle for a "
        "5-lap Practice session — None means quality gates "
        "rejected the input"
    )
    return out


# -- bundle directory exists ------------------------------------------


def test_practice_finalize_returns_bundle_dir(tmp_path: Path) -> None:
    """Returns a real directory under output root."""
    bundle = _finalize_practice(tmp_path)
    assert bundle.is_dir()
    assert bundle.resolve().is_relative_to(tmp_path.resolve())


# -- required Bundle v2 files ----------------------------------------


def test_practice_bundle_has_manifest_json(tmp_path: Path) -> None:
    """T026: Bundle v2 contains ``manifest.json`` when the
    manifest path is used."""
    bundle = _finalize_practice(tmp_path)
    manifest_path = bundle / "manifest.json"
    assert manifest_path.is_file(), (
        f"Practice bundle missing manifest.json at {manifest_path}"
    )
    assert manifest_path.stat().st_size > 0


def test_practice_bundle_has_telemetry_parquet(
    tmp_path: Path,
) -> None:
    """T027: telemetry samples land in ``telemetry.parquet``."""
    bundle = _finalize_practice(tmp_path)
    telemetry = bundle / "telemetry.parquet"
    assert telemetry.is_file(), (
        f"Practice bundle missing telemetry.parquet at {telemetry}"
    )
    assert telemetry.stat().st_size > 0


def test_practice_bundle_has_laps_parquet(tmp_path: Path) -> None:
    """T028: per-lap records land in ``laps.parquet`` when
    laps are supplied."""
    bundle = _finalize_practice(tmp_path)
    laps_path = bundle / "laps.parquet"
    assert laps_path.is_file(), (
        f"Practice bundle missing laps.parquet at {laps_path}"
    )
    assert laps_path.stat().st_size > 0


# -- manifest content -------------------------------------------------


def test_practice_manifest_records_sim_practice_environment(
    tmp_path: Path,
) -> None:
    """The v2 manifest's ``environment_tag`` must be
    ``sim_practice`` — that's how downstream consumers know
    this was a Practice session (not a Race / Qualifying)."""
    bundle = _finalize_practice(tmp_path)
    data = json.loads(
        (bundle / "manifest.json").read_text(encoding="utf-8")
    )
    text = json.dumps(data)
    # SIM_PRACTICE serializes as 'sim_practice' (or the enum
    # value name, depending on Pydantic config) — accept
    # either common form.
    has_practice_tag = (
        "sim_practice" in text.lower()
        or "SIM_PRACTICE" in text
        or "practice" in text.lower()
    )
    assert has_practice_tag, (
        f"manifest must encode the SIM_PRACTICE environment "
        f"tag; manifest payload: {data}"
    )


def test_practice_manifest_records_session_id(
    tmp_path: Path,
) -> None:
    """The session_id from the input manifest must round-trip
    — proves the manifest path doesn't generate a fresh ID
    and lose the caller's identifier."""
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    fixed_id = "019dc062-29f9-71fd-b4b3-882c4401eaa1"
    bundle = fin.finalize(
        _practice_samples(),
        manifest=_practice_manifest(session_id=fixed_id),
        laps=_practice_lap_records(),
    )
    assert bundle is not None
    data = json.loads(
        (bundle / "manifest.json").read_text(encoding="utf-8")
    )
    text = json.dumps(data)
    assert fixed_id in text, (
        f"session_id {fixed_id!r} missing from manifest"
    )


# -- atomic-write contract -------------------------------------------


def test_practice_finalize_leaves_no_temp_dirs(
    tmp_path: Path,
) -> None:
    """T031: finalize writes to ``<bundle>.tmp/`` then atomic
    rename. After success, no ``.tmp`` survives."""
    _finalize_practice(tmp_path)
    leftover_temps = [
        p for p in tmp_path.rglob("*")
        if p.is_dir() and p.name.endswith(".tmp")
    ]
    assert not leftover_temps, (
        f"finalize left orphan .tmp directories: "
        f"{leftover_temps}"
    )


# -- bundle is self-consistent ---------------------------------------


def test_practice_bundle_is_self_describing(tmp_path: Path) -> None:
    """A complete Bundle v2 directory must have at minimum the
    three core files. Any one missing means a downstream
    consumer (the backend ingest) will reject it."""
    bundle = _finalize_practice(tmp_path)
    required = ["manifest.json", "telemetry.parquet", "laps.parquet"]
    missing = [name for name in required if not (bundle / name).is_file()]
    assert not missing, (
        f"Bundle v2 missing required files: {missing}; "
        f"bundle contents: "
        f"{sorted(p.name for p in bundle.iterdir())}"
    )


def test_practice_bundle_telemetry_has_all_samples(
    tmp_path: Path,
) -> None:
    """The parquet must contain the right number of samples —
    catches off-by-one or buffer-truncation bugs in the
    writer."""
    pq = pytest.importorskip("pyarrow.parquet")
    bundle = _finalize_practice(tmp_path)
    table = pq.read_table(bundle / "telemetry.parquet")
    assert table.num_rows == _PRACTICE_SAMPLES, (
        f"telemetry.parquet has {table.num_rows} rows; "
        f"expected {_PRACTICE_SAMPLES} (= {_PRACTICE_LAPS} "
        f"laps × {_SAMPLES_PER_LAP} samples)"
    )


def test_practice_bundle_laps_match_input(tmp_path: Path) -> None:
    """``laps.parquet`` must contain one row per Practice lap
    we recorded — catches lap-record-loss bugs in the writer."""
    pq = pytest.importorskip("pyarrow.parquet")
    bundle = _finalize_practice(tmp_path)
    table = pq.read_table(bundle / "laps.parquet")
    assert table.num_rows == _PRACTICE_LAPS, (
        f"laps.parquet has {table.num_rows} rows; expected "
        f"{_PRACTICE_LAPS}"
    )
