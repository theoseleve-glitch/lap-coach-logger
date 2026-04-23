"""Tests for Le Mans Ultimate DuckDB recording import."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from lap_coach_logger.config.models import AppConfig
from lap_coach_logger.core.lmu_import import import_lmu_recording


class _FakeCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.description = [(key,) for key in rows[0].keys()] if rows else []

    def fetchall(self) -> list[tuple[object, ...]]:
        return [tuple(row.values()) for row in self._rows]


class _FakeConnection:
    def __init__(self, tables: dict[str, list[dict[str, object]]]) -> None:
        self._tables = tables

    def execute(self, query: str) -> _FakeCursor:
        compact = " ".join(query.strip().split())
        if compact == "SHOW TABLES":
            return _FakeCursor([{"name": name} for name in self._tables])
        if compact == "SELECT version() AS version":
            return _FakeCursor([{"version": "fake-duckdb-1.0"}])

        count_match = re.match(r'SELECT COUNT\(\*\) AS row_count FROM "([^"]+)"', compact)
        if count_match:
            table = count_match.group(1)
            return _FakeCursor([{"row_count": len(self._tables[table])}])

        select_match = re.match(r'SELECT \* FROM "([^"]+)"(?: LIMIT (\d+))?', compact)
        if select_match:
            table = select_match.group(1)
            limit = select_match.group(2)
            rows = list(self._tables[table])
            if limit == "0" and rows:
                # Preserve column metadata without returning data rows.
                return _FakeCursor([{key: None for key in rows[0].keys()}])
            if limit is not None:
                rows = rows[: int(limit)]
            return _FakeCursor(rows)

        raise AssertionError(f"Unexpected query: {query}")

    def close(self) -> None:
        return


class _FakeDuckDBModule:
    def __init__(self, tables: dict[str, list[dict[str, object]]]) -> None:
        self._tables = tables

    def connect(self, _path: str, read_only: bool = True) -> _FakeConnection:  # noqa: ARG002
        return _FakeConnection(self._tables)


def _build_long_table_rows(samples: int = 30) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for idx in range(samples):
        t = round(idx * 0.1, 3)
        channel_values = {
            "GPS Time": t,
            "Lap": 1 if idx < 15 else 2,
            "Lap Dist": float(idx * 120.0),
            "Ground Speed": 40.0 + idx,
            "Throttle Pos": 0.65,
            "Brake Pos": 0.05 if idx % 7 == 0 else 0.0,
            "Steered Angle": 2.0,
            "Gear": 4,
            "Engine RPM": 5200.0 + idx,
            "Fuel Level": 70.0 - idx * 0.1,
            "Track Temperature": 27.0,
            "Ambient Temperature": 19.0,
            "Engine Water Temp": 88.0,
            "In Pits": 0,
            "Lateral Acceleration": 1.1,
            "Longitudinal Acceleration": 0.2,
        }
        for name, value in channel_values.items():
            rows.append(
                {
                    "sample_time": t,
                    "channel_name": name,
                    "value": value,
                }
            )
    return rows


def test_import_lmu_recording_from_long_table(tmp_path: Path, monkeypatch) -> None:
    recording = tmp_path / "recording.duckdb"
    recording.write_bytes(b"fake duckdb")
    output_root = tmp_path / "sessions"

    fake_tables = {
        "metadata": [
            {
                "track_name": "Le Mans",
                "car_name": "Toyota GR010",
                "session_type": "Race",
                "driver_name": "Test Driver",
            }
        ],
        "telemetry_channels": _build_long_table_rows(),
        "events": [
            {
                "event_time": 0.0,
                "event_name": "Lap Started",
                "lap": 1,
            },
            {
                "event_time": 1.5,
                "event_name": "Lap Completed",
                "lap": 1,
            },
        ],
    }

    monkeypatch.setattr(
        "lap_coach_logger.core.lmu_import._load_duckdb_module",
        lambda: _FakeDuckDBModule(fake_tables),
    )

    bundle = import_lmu_recording(
        recording,
        output_root=output_root,
        config=AppConfig(output_dir=str(output_root)),
    )

    assert (bundle / "session.json").exists()
    assert (bundle / "telemetry.parquet").exists() or (bundle / "telemetry.csv").exists()
    assert (bundle / "channels_lmu_raw.json").exists()
    assert (bundle / "session_info_lmu.json").exists()
    assert (bundle / "telemetry_lmu_raw.duckdb").exists()
    assert (bundle / "lmu_recording_inspection.json").exists()

    manifest = json.loads((bundle / "session.json").read_text(encoding="utf-8"))
    # v2: fields are nested under raw_source and session blocks
    assert manifest["raw_source"]["sim_display_name"] == "Le Mans Ultimate"
    assert manifest["raw_source"]["raw_track"] == "Le Mans"
    assert manifest["raw_source"]["raw_car"] == "Toyota GR010"
    assert manifest["session"]["driver_name"] == "Test Driver"
    # LMU artifacts are attached via source_metadata
    assert manifest["source_metadata"]["import_source"] == "lmu_duckdb"
    assert manifest["source_metadata"]["lmu_raw_files"]["telemetry_lmu_raw_duckdb"] == "telemetry_lmu_raw.duckdb"

    import pyarrow.parquet as pq
    tel_path = bundle / "telemetry.parquet"
    table = pq.read_table(tel_path)
    assert table.num_rows > 0, "LMU import should produce normalized telemetry rows"
    assert table.column("sim")[0].as_py() == "Le Mans Ultimate"
    assert table.column("track_name")[0].as_py() == "Le Mans"
    assert table.column("car_name")[0].as_py() == "Toyota GR010"
