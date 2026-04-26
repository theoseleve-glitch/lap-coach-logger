"""T202: Integration test — full Sprint session (short-format
race) from sim-start → finalize.

A Sprint session is a short-format competitive race —
typically 15-25 minutes / 10-20 laps. The v2 schema
encodes the racing environment as ``EnvironmentTag.SIM_RACE``;
the Sprint vs Endurance distinction is carried in duration +
sample count rather than a separate enum value.

This test exercises the same Bundle v2 finalize plumbing as
T201 (Practice) but with the SIM_RACE environment tag and
race-typical lap counts — catches any race-specific writer
code paths (out-lap classification, lap-validity heuristics
for race traffic) that Practice's open-lap session misses.

Same shape as T201: real production code paths, real disk
writes via tmp_path, no mocks.
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


_SPRINT_LAPS = 12
_SAMPLES_PER_LAP = 80  # ~80s lap at 1 Hz — Sprint pace
_SPRINT_SAMPLES = _SPRINT_LAPS * _SAMPLES_PER_LAP  # 960
_SPRINT_DURATION_S = float(_SPRINT_SAMPLES)

_STARTED = datetime(2026, 4, 24, 14, 0, 0, tzinfo=timezone.utc)
_ENDED = _STARTED + timedelta(seconds=_SPRINT_DURATION_S)


# -- fixtures --------------------------------------------------------


def _sprint_manifest(
    *,
    session_id: str | None = None,
) -> SessionManifest:
    """Build a SessionManifest tagged for a Sprint race
    (``EnvironmentTag.SIM_RACE`` — the v2 schema's racing
    environment)."""
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
        sim_title="iracing",
        real_hardware=None,
        car_id=uuid6.uuid7(),
        track_id=uuid6.uuid7(),
        track_layout="monza-grand-prix",
        environment_tag=EnvironmentTag.SIM_RACE,
        objective_tag=None,
        training_block_id=None,
        started_at=_STARTED,
        ended_at=_ENDED,
        duration_seconds=_SPRINT_DURATION_S,
        telemetry_checksums={},
        total_samples=_SPRINT_SAMPLES,
        sample_rate_hz=1.0,
        data_quality=DataQuality(
            score=92.0,
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


def _sprint_samples() -> list[TelemetrySample]:
    """Synthetic Sprint race telemetry: 12 laps × 80 samples
    each. Slight per-lap variance so the writer doesn't see
    purely-identical data."""
    out: list[TelemetrySample] = []
    for global_idx in range(_SPRINT_SAMPLES):
        lap_num = 1 + (global_idx // _SAMPLES_PER_LAP)
        idx_in_lap = global_idx % _SAMPLES_PER_LAP
        out.append(
            TelemetrySample(
                timestamp_utc=(
                    _STARTED + timedelta(seconds=global_idx)
                ).isoformat(),
                sim="iracing",
                session_uid="sprint-e2e",
                session_time_s=float(global_idx),
                lap_number=lap_num,
                lap_distance_m=float(idx_in_lap * 75),
                lap_dist_pct=idx_in_lap / _SAMPLES_PER_LAP,
                speed_kph=160.0 + float(global_idx % 12),
                throttle_pct=0.65 + float(global_idx % 5) * 0.05,
                brake_pct=0.10 if global_idx % 9 == 0 else 0.0,
                steering_deg=float((-4 + (global_idx % 9)) * 1.5),
                gear=4 + (global_idx % 3),
                rpm=6200.0 + float(global_idx % 500),
                world_pos_x=float(global_idx),
                world_pos_y=0.0,
                world_pos_z=float(idx_in_lap),
                yaw_deg=float(global_idx % 360),
                long_accel_g=0.20,
                lat_accel_g=0.25,
                is_on_track=True,
                is_in_pits=False,
                track_name="Monza",
                car_name="GT3",
                session_type="Sprint",
            )
        )
    return out


def _sprint_lap_records() -> list[LegacyLapRecord]:
    """One LegacyLapRecord per Sprint lap. Lap 1 is the
    out-lap from the formation lap; the rest are flying race
    laps (clean unless the AI has shenanigans)."""
    records: list[LegacyLapRecord] = []
    for lap_num in range(1, _SPRINT_LAPS + 1):
        start_s = float((lap_num - 1) * _SAMPLES_PER_LAP)
        end_s = float(lap_num * _SAMPLES_PER_LAP)
        records.append(LegacyLapRecord(
            lap_number=lap_num,
            start_session_time_s=start_s,
            end_session_time_s=end_s,
            lap_time_s=end_s - start_s,
            out_lap=(lap_num == 1),
            in_lap=(lap_num == _SPRINT_LAPS),
            invalid=False,
            classification="race-clean" if lap_num > 1 else "out",
            has_complete_telemetry=True,
            valid_for_analysis=(lap_num != 1 and lap_num != _SPRINT_LAPS),
            lap_time_valid=(lap_num != 1),
            likely_flying_lap=(lap_num != 1 and lap_num != _SPRINT_LAPS),
            clean_lap=(lap_num != 1 and lap_num != _SPRINT_LAPS),
            sample_count=_SAMPLES_PER_LAP,
            max_speed_kph=210.0 + float(lap_num),
        ))
    return records


def _finalize_sprint(tmp_path: Path) -> Path:
    """Run a complete Sprint finalize. Returns the bundle dir."""
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(
        _sprint_samples(),
        manifest=_sprint_manifest(),
        laps=_sprint_lap_records(),
    )
    assert out is not None, (
        "finalize(manifest=...) must produce a bundle for a "
        "12-lap Sprint race — None means quality gates "
        "rejected the input"
    )
    return out


# -- bundle directory exists -----------------------------------------


def test_sprint_finalize_returns_bundle_dir(tmp_path: Path) -> None:
    """Returns a real directory under output root."""
    bundle = _finalize_sprint(tmp_path)
    assert bundle.is_dir()
    assert bundle.resolve().is_relative_to(tmp_path.resolve())


# -- required Bundle v2 files ---------------------------------------


def test_sprint_bundle_has_manifest_json(tmp_path: Path) -> None:
    """T026: Bundle v2 contains ``manifest.json`` with the
    SIM_RACE manifest passed in."""
    bundle = _finalize_sprint(tmp_path)
    manifest_path = bundle / "manifest.json"
    assert manifest_path.is_file()
    assert manifest_path.stat().st_size > 0


def test_sprint_bundle_has_telemetry_parquet(
    tmp_path: Path,
) -> None:
    """T027: 960-sample Sprint produces a non-empty
    telemetry.parquet."""
    bundle = _finalize_sprint(tmp_path)
    telemetry = bundle / "telemetry.parquet"
    assert telemetry.is_file()
    assert telemetry.stat().st_size > 0


def test_sprint_bundle_has_laps_parquet(tmp_path: Path) -> None:
    """T028: 12 lap records produce a non-empty laps.parquet."""
    bundle = _finalize_sprint(tmp_path)
    laps_path = bundle / "laps.parquet"
    assert laps_path.is_file()
    assert laps_path.stat().st_size > 0


# -- manifest content ------------------------------------------------


def test_sprint_manifest_records_sim_race_environment(
    tmp_path: Path,
) -> None:
    """The v2 manifest's ``environment_tag`` must be
    ``sim_race`` for a Sprint — Sprint and Endurance both
    share the SIM_RACE tag (format distinguished by duration,
    not enum value)."""
    bundle = _finalize_sprint(tmp_path)
    data = json.loads(
        (bundle / "manifest.json").read_text(encoding="utf-8")
    )
    text = json.dumps(data)
    has_race_tag = (
        "sim_race" in text.lower()
        or "SIM_RACE" in text
    )
    assert has_race_tag, (
        f"Sprint manifest must encode the SIM_RACE environment "
        f"tag (got payload: {data})"
    )


def test_sprint_manifest_records_session_id(tmp_path: Path) -> None:
    """The session_id from the input manifest round-trips."""
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    fixed_id = "019dc063-29f9-71fd-b4b3-882c4401eaa2"
    bundle = fin.finalize(
        _sprint_samples(),
        manifest=_sprint_manifest(session_id=fixed_id),
        laps=_sprint_lap_records(),
    )
    assert bundle is not None
    text = (bundle / "manifest.json").read_text(encoding="utf-8")
    assert fixed_id in text


# -- atomic-write contract ------------------------------------------


def test_sprint_finalize_leaves_no_temp_dirs(
    tmp_path: Path,
) -> None:
    """T031: no .tmp dirs survive successful finalize."""
    _finalize_sprint(tmp_path)
    leftover_temps = [
        p for p in tmp_path.rglob("*")
        if p.is_dir() and p.name.endswith(".tmp")
    ]
    assert not leftover_temps, (
        f"finalize left orphan .tmp directories: {leftover_temps}"
    )


# -- self-consistency -----------------------------------------------


def test_sprint_bundle_is_self_describing(tmp_path: Path) -> None:
    """All three required Bundle v2 files present together."""
    bundle = _finalize_sprint(tmp_path)
    required = ["manifest.json", "telemetry.parquet", "laps.parquet"]
    missing = [n for n in required if not (bundle / n).is_file()]
    assert not missing, (
        f"Bundle v2 missing required files: {missing}; "
        f"bundle contents: "
        f"{sorted(p.name for p in bundle.iterdir())}"
    )


def test_sprint_bundle_telemetry_has_all_samples(
    tmp_path: Path,
) -> None:
    """Exact row count: 12 laps × 80 samples = 960. Catches
    off-by-one or buffer-truncation in the writer."""
    pq = pytest.importorskip("pyarrow.parquet")
    bundle = _finalize_sprint(tmp_path)
    table = pq.read_table(bundle / "telemetry.parquet")
    assert table.num_rows == _SPRINT_SAMPLES, (
        f"telemetry.parquet has {table.num_rows} rows; "
        f"expected {_SPRINT_SAMPLES}"
    )


def test_sprint_bundle_laps_match_input(tmp_path: Path) -> None:
    """laps.parquet has exactly 12 rows (no lap-record loss)."""
    pq = pytest.importorskip("pyarrow.parquet")
    bundle = _finalize_sprint(tmp_path)
    table = pq.read_table(bundle / "laps.parquet")
    assert table.num_rows == _SPRINT_LAPS, (
        f"laps.parquet has {table.num_rows} rows; expected "
        f"{_SPRINT_LAPS}"
    )


# -- race-specific lap classification --------------------------------


def test_sprint_lap_records_include_in_lap_classification(
    tmp_path: Path,
) -> None:
    """The final lap of a Sprint race is the in-lap (after
    chequered flag, drive back to pits). The writer must
    preserve the in_lap=True flag from the input record so
    downstream analysis can exclude it from pace stats."""
    pq = pytest.importorskip("pyarrow.parquet")
    bundle = _finalize_sprint(tmp_path)
    table = pq.read_table(bundle / "laps.parquet")
    df = table.to_pandas()
    # The final lap (lap_number == _SPRINT_LAPS) must be
    # marked as in_lap.
    last_lap = df[df["lap_number"] == _SPRINT_LAPS].iloc[0]
    assert bool(last_lap["in_lap"]) is True, (
        f"final Sprint lap (#{_SPRINT_LAPS}) must be marked "
        f"in_lap=True (chequered-flag drive back to pits); "
        f"row: {last_lap.to_dict()}"
    )
    # And the first lap must be marked as out-lap.
    first_lap = df[df["lap_number"] == 1].iloc[0]
    assert bool(first_lap["out_lap"]) is True, (
        f"first Sprint lap must be marked out_lap=True "
        f"(rolling/formation lap); row: {first_lap.to_dict()}"
    )
