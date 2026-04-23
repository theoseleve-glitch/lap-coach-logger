from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from lap_coach_logger.core.session_export import export_session_telemetry_csv
from lap_coach_logger.writers.finalizer import SessionFinalizer

from tests.helpers import finalize_session, make_quality_samples


def test_export_session_telemetry_csv_copies_existing_csv(tmp_path: Path) -> None:
    bundle = finalize_session(tmp_path / "sessions", session_uid="export-csv")
    export_path = tmp_path / "export.csv"

    ok = export_session_telemetry_csv(bundle, export_path)

    assert ok is True
    assert export_path.exists()
    with export_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert rows
    assert "timestamp_utc" in rows[0]


def test_export_session_telemetry_csv_converts_parquet_without_pandas(tmp_path: Path) -> None:
    finalizer = SessionFinalizer(tmp_path / "sessions")
    now = datetime.now(timezone.utc)

    with patch(
        "lap_coach_logger.writers.finalizer.CsvWriter.write_samples",
        side_effect=RuntimeError("Simulated csv failure"),
    ):
        bundle = finalizer.finalize(
            make_quality_samples(session_uid="export-parquet"),
            started_at=now,
            sim="iRacing",
            track="Spa",
            session_type="Race",
            session_uid="export-parquet",
            extra_metadata={"car": "GT3", "sample_rate_hz": 1.0},
        )

    assert bundle is not None
    assert (bundle / "telemetry.parquet").exists()
    assert not (bundle / "telemetry.csv").exists()

    export_path = tmp_path / "converted.csv"
    ok = export_session_telemetry_csv(bundle, export_path)

    assert ok is True
    assert export_path.exists()
    with export_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert rows
    assert rows[0]["sim"] == "iRacing"
