"""Tests for writer fallback: Parquet primary, CSV fallback, metadata, folder naming."""

import json
from pathlib import Path
from unittest.mock import patch

from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.writers.finalizer import (
    SessionFinalizer,
    _safe_slug,
    _validate_samples,
    session_folder_name,
)

from datetime import datetime, timezone


def _make_samples(n: int = 5) -> list[TelemetrySample]:
    return [
        TelemetrySample(sim="iRacing", speed_kph=float(i * 20), gear=i % 6)
        for i in range(n)
    ]


def test_parquet_write_succeeds(tmp_path: Path) -> None:
    """Default finalization writes parquet as the primary telemetry format."""
    finalizer = SessionFinalizer(tmp_path)
    now = datetime.now(timezone.utc)
    result = finalizer.finalize(
        _make_samples(),
        started_at=now,
        sim="iRacing",
        track="Spa",
        session_type="race",
        session_uid="test123",
    )
    assert result is not None
    assert (result / "telemetry.parquet").exists()
    assert not (result / "telemetry.csv").exists()
    assert (result / "session.json").exists()

    manifest = json.loads((result / "session.json").read_text())
    # v2 format checks
    assert manifest["schema_version"] == 2
    assert manifest["logger_version"] is not None
    assert manifest["session"]["duration_s"] >= 0
    assert manifest["session"]["start_time"] is not None
    assert manifest["session"]["end_time"] is not None
    assert manifest["raw_source"]["sim_id"] == "iracing"
    assert manifest["raw_source"]["raw_track"] == "Spa"


def test_csv_fallback_on_parquet_failure(tmp_path: Path) -> None:
    """When parquet write fails, CSV is produced as fallback."""
    finalizer = SessionFinalizer(tmp_path)
    now = datetime.now(timezone.utc)

    with patch(
        "lap_coach_logger.writers.finalizer.ParquetWriter",
        side_effect=RuntimeError("Simulated parquet failure"),
    ):
        result = finalizer.finalize(
            _make_samples(),
            started_at=now,
            sim="ACC",
            track="Monza",
            session_type="practice",
        )

    assert result is not None
    assert (result / "telemetry.csv").exists()
    assert not (result / "telemetry.parquet").exists()

    manifest = json.loads((result / "session.json").read_text())
    # v2 format: CSV fallback still produces session.json
    assert manifest["schema_version"] == 2


def test_debug_csv_export(tmp_path: Path) -> None:
    """When debug_csv_export is True, a debug CSV is written alongside parquet."""
    finalizer = SessionFinalizer(tmp_path, debug_csv_export=True)
    now = datetime.now(timezone.utc)
    result = finalizer.finalize(
        _make_samples(),
        started_at=now,
        sim="iRacing",
        track="Spa",
        session_type="race",
    )
    assert result is not None
    assert (result / "telemetry.parquet").exists()
    assert (result / "telemetry_debug.csv").exists()


def test_stale_temp_cleanup(tmp_path: Path) -> None:
    stale = tmp_path / "_tmp_old_session"
    stale.mkdir()
    (stale / "metadata.json").write_text("{}")

    cleaned = SessionFinalizer.cleanup_stale_temps(tmp_path)
    assert cleaned == 1
    assert not stale.exists()


# -- folder naming / sanitisation --

def test_safe_slug_basic() -> None:
    assert _safe_slug("Spa-Francorchamps") == "Spa-Francorchamps"
    assert _safe_slug("Nürburgring GP") == "N_rburgring_GP"
    assert _safe_slug(None) == "unknown"
    assert _safe_slug("") == "unknown"
    assert _safe_slug("a/b\\c:d*e") == "a_b_c_d_e"


def test_safe_slug_collapses_underscores() -> None:
    assert _safe_slug("foo   bar") == "foo_bar"
    assert _safe_slug("___") == "unknown"


def test_session_folder_name_format() -> None:
    dt = datetime(2025, 3, 15, 14, 30, 0, tzinfo=timezone.utc)
    name = session_folder_name(dt, "iRacing", "Spa", "Race")
    assert name == "2025-03-15_14-30-00__iRacing__Spa__Race"


# -- schema validation --

def test_validate_samples_ok() -> None:
    warnings = _validate_samples(_make_samples(3))
    assert warnings == []


def test_validate_samples_empty() -> None:
    warnings = _validate_samples([])
    assert len(warnings) == 1
    assert "No samples" in warnings[0]


# -- metadata enriched fields --

def test_session_has_enriched_fields(tmp_path: Path) -> None:
    finalizer = SessionFinalizer(tmp_path)
    now = datetime.now(timezone.utc)
    result = finalizer.finalize(
        _make_samples(),
        started_at=now,
        sim="ACC",
        track="Monza",
        session_type="Qualify",
        extra_metadata={"car": "Porsche 911", "sample_rate_hz": 10.0, "dropped_samples": 2},
    )
    assert result is not None
    manifest = json.loads((result / "session.json").read_text())
    # v2: car is in raw_source
    assert manifest["raw_source"]["raw_car"] == "Porsche 911"
    assert manifest["session"]["sample_count"] == 5
