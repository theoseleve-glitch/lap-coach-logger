"""T203: Integration test — full 30-minute Endurance session
from sim-start → finalize.

Endurance differs from Sprint (T202) in two key dimensions:

1. **Duration / sample count.** 30 min at 1 Hz = 1800 samples.
   The v2 schema's environment vocabulary is coarse — both
   Sprint and Endurance use ``EnvironmentTag.SIM_RACE``;
   the format distinction is recoverable from
   ``duration_seconds`` and ``total_samples``.

2. **Pit stops.** A 30-minute race typically requires at
   least one pit stop. The writer must preserve
   ``LegacyLapRecord.pit_entry_or_exit_detected`` through the
   parquet round-trip — Sprint sessions don't usually pit, so
   T202 doesn't exercise this path.

Same fixtures pattern as T201 / T202: real production code
paths, real disk writes via tmp_path, no mocks.
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


_ENDURANCE_LAPS = 18
_SAMPLES_PER_LAP = 100  # ~100s lap at 1 Hz
_ENDURANCE_SAMPLES = _ENDURANCE_LAPS * _SAMPLES_PER_LAP  # 1800 = 30 min
_ENDURANCE_DURATION_S = float(_ENDURANCE_SAMPLES)
_PIT_LAP = 9  # Mid-session pit stop

_STARTED = datetime(2026, 4, 24, 18, 0, 0, tzinfo=timezone.utc)
_ENDED = _STARTED + timedelta(seconds=_ENDURANCE_DURATION_S)


# -- fixtures --------------------------------------------------------


def _endurance_manifest(
    *,
    session_id: str | None = None,
) -> SessionManifest:
    """Build a SessionManifest tagged for an Endurance race
    (``EnvironmentTag.SIM_RACE`` — same as Sprint; the format
    is encoded via duration + sample count)."""
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
        track_layout="le-mans-circuit-de-la-sarthe",
        environment_tag=EnvironmentTag.SIM_RACE,
        objective_tag=None,
        training_block_id=None,
        started_at=_STARTED,
        ended_at=_ENDED,
        duration_seconds=_ENDURANCE_DURATION_S,
        telemetry_checksums={},
        total_samples=_ENDURANCE_SAMPLES,
        sample_rate_hz=1.0,
        data_quality=DataQuality(
            score=90.0,
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


def _endurance_samples() -> list[TelemetrySample]:
    """Synthetic Endurance race telemetry: 18 laps × 100
    samples each = 1800 samples = 30 min at 1 Hz."""
    out: list[TelemetrySample] = []
    for global_idx in range(_ENDURANCE_SAMPLES):
        lap_num = 1 + (global_idx // _SAMPLES_PER_LAP)
        idx_in_lap = global_idx % _SAMPLES_PER_LAP
        # Pit lap: speed drops, brake stays on briefly
        on_pit_lap = lap_num == _PIT_LAP
        in_pit_box = on_pit_lap and (40 <= idx_in_lap <= 55)
        out.append(
            TelemetrySample(
                timestamp_utc=(
                    _STARTED + timedelta(seconds=global_idx)
                ).isoformat(),
                sim="iracing",
                session_uid="endurance-e2e",
                session_time_s=float(global_idx),
                lap_number=lap_num,
                lap_distance_m=float(idx_in_lap * 60),
                lap_dist_pct=idx_in_lap / _SAMPLES_PER_LAP,
                speed_kph=(
                    20.0 if in_pit_box
                    else 170.0 + float(global_idx % 14)
                ),
                throttle_pct=(
                    0.0 if in_pit_box
                    else 0.62 + float(global_idx % 5) * 0.05
                ),
                brake_pct=(
                    0.30 if in_pit_box
                    else (0.10 if global_idx % 11 == 0 else 0.0)
                ),
                steering_deg=float((-3 + (global_idx % 8)) * 1.4),
                gear=2 if in_pit_box else 4 + (global_idx % 3),
                rpm=2200.0 if in_pit_box else 6400.0 + float(global_idx % 400),
                world_pos_x=float(global_idx),
                world_pos_y=0.0,
                world_pos_z=float(idx_in_lap),
                yaw_deg=float(global_idx % 360),
                long_accel_g=0.10 if in_pit_box else 0.18,
                lat_accel_g=0.05 if in_pit_box else 0.22,
                is_on_track=True,
                is_in_pits=in_pit_box,
                track_name="Le Mans",
                car_name="LMP2",
                session_type="Endurance",
            )
        )
    return out


def _endurance_lap_records() -> list[LegacyLapRecord]:
    """One LegacyLapRecord per Endurance lap. Lap 1 = out-lap;
    Lap 9 = pit-stop lap (pit_entry_or_exit_detected=True);
    final lap = in-lap."""
    records: list[LegacyLapRecord] = []
    for lap_num in range(1, _ENDURANCE_LAPS + 1):
        start_s = float((lap_num - 1) * _SAMPLES_PER_LAP)
        end_s = float(lap_num * _SAMPLES_PER_LAP)
        is_out_lap = lap_num == 1
        is_in_lap = lap_num == _ENDURANCE_LAPS
        is_pit_lap = lap_num == _PIT_LAP
        records.append(LegacyLapRecord(
            lap_number=lap_num,
            start_session_time_s=start_s,
            end_session_time_s=end_s,
            lap_time_s=end_s - start_s,
            out_lap=is_out_lap,
            in_lap=is_in_lap,
            invalid=False,
            classification=(
                "pit" if is_pit_lap
                else ("out" if is_out_lap else "race-clean")
            ),
            has_complete_telemetry=True,
            valid_for_analysis=(
                not (is_out_lap or is_in_lap or is_pit_lap)
            ),
            pit_entry_or_exit_detected=is_pit_lap,
            lap_time_valid=not is_out_lap,
            likely_flying_lap=(
                not (is_out_lap or is_in_lap or is_pit_lap)
            ),
            clean_lap=(
                not (is_out_lap or is_in_lap or is_pit_lap)
            ),
            sample_count=_SAMPLES_PER_LAP,
            max_speed_kph=(
                180.0 if is_pit_lap else 220.0 + float(lap_num)
            ),
        ))
    return records


def _finalize_endurance(tmp_path: Path) -> Path:
    """Run a complete Endurance finalize. Returns the bundle dir."""
    fin = SessionFinalizer(tmp_path, quality_config=QualityConfig())
    out = fin.finalize(
        _endurance_samples(),
        manifest=_endurance_manifest(),
        laps=_endurance_lap_records(),
    )
    assert out is not None, (
        "finalize(manifest=...) must produce a bundle for an "
        "18-lap, 30-minute Endurance race — None means quality "
        "gates rejected the input"
    )
    return out


# -- bundle directory exists -----------------------------------------


def test_endurance_finalize_returns_bundle_dir(
    tmp_path: Path,
) -> None:
    bundle = _finalize_endurance(tmp_path)
    assert bundle.is_dir()
    assert bundle.resolve().is_relative_to(tmp_path.resolve())


# -- required Bundle v2 files ---------------------------------------


def test_endurance_bundle_has_manifest_json(tmp_path: Path) -> None:
    bundle = _finalize_endurance(tmp_path)
    assert (bundle / "manifest.json").is_file()
    assert (bundle / "manifest.json").stat().st_size > 0


def test_endurance_bundle_has_telemetry_parquet(
    tmp_path: Path,
) -> None:
    bundle = _finalize_endurance(tmp_path)
    assert (bundle / "telemetry.parquet").is_file()
    assert (bundle / "telemetry.parquet").stat().st_size > 0


def test_endurance_bundle_has_laps_parquet(tmp_path: Path) -> None:
    bundle = _finalize_endurance(tmp_path)
    assert (bundle / "laps.parquet").is_file()
    assert (bundle / "laps.parquet").stat().st_size > 0


# -- manifest content -----------------------------------------------


def test_endurance_manifest_records_sim_race_environment(
    tmp_path: Path,
) -> None:
    """Endurance shares the SIM_RACE tag with Sprint — the
    schema's coarseness is intentional; format is recoverable
    from duration_seconds + total_samples."""
    bundle = _finalize_endurance(tmp_path)
    text = (bundle / "manifest.json").read_text(encoding="utf-8")
    assert (
        "sim_race" in text.lower() or "SIM_RACE" in text
    ), f"Endurance manifest missing SIM_RACE tag; payload: {text}"


def test_endurance_manifest_records_endurance_duration(
    tmp_path: Path,
) -> None:
    """The 30-minute (1800s) duration must round-trip through
    the manifest — that's how downstream tooling distinguishes
    Endurance from Sprint without a separate enum value."""
    bundle = _finalize_endurance(tmp_path)
    data = json.loads(
        (bundle / "manifest.json").read_text(encoding="utf-8")
    )
    text = json.dumps(data)
    # Duration may be encoded as 1800.0, 1800, or in a nested
    # format. Pin by string match.
    assert "1800" in text, (
        f"Endurance duration (1800s) missing from manifest "
        f"payload: {data}"
    )


# -- atomic-write contract ------------------------------------------


def test_endurance_finalize_leaves_no_temp_dirs(
    tmp_path: Path,
) -> None:
    """T031: no .tmp dirs survive even at 1800-sample volume."""
    _finalize_endurance(tmp_path)
    leftover_temps = [
        p for p in tmp_path.rglob("*")
        if p.is_dir() and p.name.endswith(".tmp")
    ]
    assert not leftover_temps, (
        f"finalize left orphan .tmp directories: {leftover_temps}"
    )


# -- volume + structure ---------------------------------------------


def test_endurance_bundle_telemetry_has_all_samples(
    tmp_path: Path,
) -> None:
    """Exact row count: 18 × 100 = 1800. At Endurance volume
    the writer's behavior under larger inputs is exercised."""
    pq = pytest.importorskip("pyarrow.parquet")
    bundle = _finalize_endurance(tmp_path)
    table = pq.read_table(bundle / "telemetry.parquet")
    assert table.num_rows == _ENDURANCE_SAMPLES, (
        f"telemetry.parquet has {table.num_rows} rows; "
        f"expected {_ENDURANCE_SAMPLES}"
    )


def test_endurance_bundle_laps_match_input(tmp_path: Path) -> None:
    """laps.parquet has exactly 18 rows."""
    pq = pytest.importorskip("pyarrow.parquet")
    bundle = _finalize_endurance(tmp_path)
    table = pq.read_table(bundle / "laps.parquet")
    assert table.num_rows == _ENDURANCE_LAPS, (
        f"laps.parquet has {table.num_rows} rows; expected "
        f"{_ENDURANCE_LAPS}"
    )


# -- pit-stop preservation ------------------------------------------


def test_endurance_bundle_preserves_pit_lap_marker(
    tmp_path: Path,
) -> None:
    """The mid-session pit-stop lap (lap 9) must round-trip
    with ``pit_entry_or_exit_detected=True``. T202's no-pit
    Sprint never exercised this path; T203 catches writer
    bugs that drop pit-event metadata."""
    pq = pytest.importorskip("pyarrow.parquet")
    bundle = _finalize_endurance(tmp_path)
    table = pq.read_table(bundle / "laps.parquet")
    df = table.to_pandas()

    pit_lap_row = df[df["lap_number"] == _PIT_LAP].iloc[0]
    assert bool(pit_lap_row["pit_entry_or_exit_detected"]) is True, (
        f"pit-stop lap (#{_PIT_LAP}) lost its "
        f"pit_entry_or_exit_detected flag through the parquet "
        f"round-trip; row: {pit_lap_row.to_dict()}"
    )

    # Non-pit racing laps must NOT have the flag set —
    # otherwise the marker is meaningless.
    racing_laps = df[
        (df["lap_number"] != _PIT_LAP)
        & (df["lap_number"] != 1)  # exclude out-lap
        & (df["lap_number"] != _ENDURANCE_LAPS)  # exclude in-lap
    ]
    pit_flagged = racing_laps[
        racing_laps["pit_entry_or_exit_detected"] == True  # noqa: E712
    ]
    assert len(pit_flagged) == 0, (
        f"non-pit racing laps unexpectedly flagged with "
        f"pit_entry_or_exit_detected=True: "
        f"{pit_flagged['lap_number'].tolist()}"
    )
