"""Tests for writer fallback: CSV failure → Parquet, metadata, folder naming."""

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


def test_csv_write_succeeds(tmp_path: Path) -> None:
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
    assert (result / "telemetry.csv").exists()
    assert (result / "metadata.json").exists()

    meta = json.loads((result / "metadata.json").read_text())
    assert meta["save_format"] == "csv"
    assert meta["sample_count"] == 5
    assert meta["app_version"] is not None
    assert meta["logger_version"] is not None
    assert meta["duration_s"] >= 0
    assert "started_at_utc" in meta
    assert "ended_at_utc" in meta
    assert meta["sim"] == "iRacing"
    assert meta["track_name"] == "Spa"
    # data_quality_score: all samples have speed_kph and gear set
    assert 0.0 < meta["data_quality_score"] <= 1.0


def test_parquet_fallback_on_csv_failure(tmp_path: Path) -> None:
    finalizer = SessionFinalizer(tmp_path)
    now = datetime.now(timezone.utc)

    with patch(
        "lap_coach_logger.writers.finalizer.CsvWriter.write_samples",
        side_effect=RuntimeError("Simulated csv failure"),
    ):
        result = finalizer.finalize(
            _make_samples(),
            started_at=now,
            sim="ACC",
            track="Monza",
            session_type="practice",
        )

    assert result is not None
    assert (result / "telemetry.parquet").exists()
    assert not (result / "telemetry.csv").exists()

    meta = json.loads((result / "metadata.json").read_text())
    assert meta["save_format"] == "parquet"


def test_debug_csv_export(tmp_path: Path) -> None:
    """When debug_csv_export is True, a CSV is written alongside parquet."""
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
    assert (result / "telemetry.csv").exists()
    assert not (result / "telemetry_debug.csv").exists()


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

def test_metadata_has_enriched_fields(tmp_path: Path) -> None:
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
    meta = json.loads((result / "metadata.json").read_text())
    assert meta["car_name"] == "Porsche 911"
    assert meta["sample_rate_hz"] == 10.0
    assert meta["dropped_sample_count"] == 2
    assert "output_path" in meta
