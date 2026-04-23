"""Le Mans Ultimate DuckDB recording import.

LMU officially records telemetry to DuckDB files. This module provides a
best-effort importer that converts those recordings into the logger's normal
session-bundle format for offline review.

The importer is intentionally conservative:
  - it only relies on table/column discovery that can be inferred at runtime
  - it preserves the original `.duckdb` recording inside the saved bundle
  - it stores a schema inspection JSON alongside the imported bundle
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import types
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from importlib import import_module
from pathlib import Path
from typing import Any

from lap_coach_logger.config.models import AppConfig
from lap_coach_logger.core.lap_analysis import classify_laps
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.normalization.mapper import normalise_sample
from lap_coach_logger.writers.bundle_schema import SessionEvent
from lap_coach_logger.writers.finalizer import SessionFinalizer

LMU_SIM_NAME = "Le Mans Ultimate"
LMU_RAW_SIM_NAME = "LMU"

_TIME_COLUMN_CANDIDATES = {
    "time",
    "timestamp",
    "sampletime",
    "sample_time",
    "sessiontime",
    "session_time",
    "elapsedtime",
    "elapsed_time",
    "gpstime",
    "gps_time",
}
_NAME_COLUMN_CANDIDATES = {
    "name",
    "channel",
    "channelname",
    "channel_name",
    "signal",
    "signalname",
    "signal_name",
    "metric",
    "metricname",
    "metric_name",
    "key",
}
_VALUE_COLUMN_CANDIDATES = {
    "value",
    "reading",
    "sample",
    "samplevalue",
    "sample_value",
    "numericvalue",
    "numeric_value",
}
_EVENT_COLUMN_CANDIDATES = {
    "event",
    "eventname",
    "event_name",
    "type",
    "eventtype",
    "event_type",
}

_LMU_CHANNEL_ALIASES: dict[str, str] = {
    "gpstime": "GPS Time",
    "sessiontime": "GPS Time",
    "time": "GPS Time",
    "lap": "Lap",
    "lapnumber": "Lap",
    "lapdist": "Lap Dist",
    "lapdistance": "Lap Dist",
    "groundspeed": "Ground Speed",
    "gpsspeed": "GPS Speed",
    "speed": "Ground Speed",
    "throttlepos": "Throttle Pos",
    "throttleposition": "Throttle Pos",
    "throttle": "Throttle Pos",
    "brakepos": "Brake Pos",
    "brakeposition": "Brake Pos",
    "brake": "Brake Pos",
    "steeredangle": "Steered Angle",
    "steeringangle": "Steered Angle",
    "steering": "Steered Angle",
    "gear": "Gear",
    "enginerpm": "Engine RPM",
    "rpm": "Engine RPM",
    "fuellevel": "Fuel Level",
    "fuel": "Fuel Level",
    "enginewatertemp": "Engine Water Temp",
    "watertemp": "Engine Water Temp",
    "engineoiltemp": "Engine Oil Temp",
    "oiltemp": "Engine Oil Temp",
    "tracktemperature": "Track Temperature",
    "tracktemp": "Track Temperature",
    "ambienttemperature": "Ambient Temperature",
    "airtemp": "Ambient Temperature",
    "lateralacceleration": "Lateral Acceleration",
    "lataccel": "Lateral Acceleration",
    "gforcelat": "Lateral Acceleration",
    "longitudinalacceleration": "Longitudinal Acceleration",
    "longaccel": "Longitudinal Acceleration",
    "gforcelong": "Longitudinal Acceleration",
    "inpits": "In Pits",
    "pitlane": "In Pits",
    "pitstate": "In Pits",
    "abslevel": "ABS Level",
    "tclevel": "TC Level",
}

_METADATA_KEY_ALIASES: dict[str, str] = {
    "track": "track_name",
    "trackname": "track_name",
    "venue": "track_name",
    "circuit": "track_name",
    "car": "car_name",
    "carname": "car_name",
    "vehicle": "car_name",
    "vehiclename": "car_name",
    "session": "session_type",
    "sessiontype": "session_type",
    "driver": "driver_name",
    "drivername": "driver_name",
}


class LMUImportError(RuntimeError):
    """Raised when a recording cannot be inspected or imported."""


@dataclass(frozen=True)
class TableSummary:
    name: str
    columns: list[str]
    row_count: int
    sample_rows: list[dict[str, Any]]


def import_lmu_recording(
    recording_path: str | Path,
    *,
    output_root: str | Path,
    config: AppConfig,
) -> Path:
    """Import one LMU DuckDB recording into a session bundle."""
    recording = Path(recording_path)
    if not recording.exists():
        raise LMUImportError(f"LMU recording not found: {recording}")
    if recording.suffix.lower() != ".duckdb":
        raise LMUImportError("LMU recording must be a .duckdb file")

    duckdb = _load_duckdb_module()
    conn = _connect_read_only(duckdb, recording)
    try:
        inspection = inspect_lmu_recording(recording, conn=conn)
        metadata = _extract_metadata(inspection)

        telemetry = _load_telemetry_rows(conn, inspection)
        if not telemetry.normalized_rows:
            raise LMUImportError("No recognizable LMU telemetry samples were found in the recording")

        samples = _build_samples_from_rows(
            telemetry.normalized_rows,
            recording=recording,
            metadata=metadata,
        )
        if not samples:
            raise LMUImportError("LMU telemetry recording did not yield any normalized samples")

        lap_records, lap_summary = classify_laps(samples, config=config.lap_analysis)
        started_at = datetime.fromisoformat(samples[0].timestamp_utc)
        ended_at = datetime.fromisoformat(samples[-1].timestamp_utc)

        finalizer = SessionFinalizer(
            Path(output_root),
            compression=config.writer.parquet_compression,
            debug_csv_export=config.writer.debug_csv_export,
            quality_config=config.quality,
        )

        extra_metadata = {
            "car": metadata.get("car_name") or samples[0].car_name,
            "sample_rate_hz": _estimate_sample_rate_hz(samples),
            "duration_s": round((ended_at - started_at).total_seconds(), 2),
            "lap_count": lap_summary.total_laps,
            "total_laps": lap_summary.total_laps,
            "valid_laps": lap_summary.valid_laps,
            "clean_laps": lap_summary.clean_laps,
            "best_lap_time_s": lap_summary.best_lap_time_s,
            "best_clean_lap_time_s": lap_summary.best_clean_lap_time_s,
            "representative_lap_number": lap_summary.representative_lap_number,
            "representative_lap_time_s": lap_summary.representative_lap_time_s,
            "import_source": "lmu_duckdb",
            "imported_from_file": str(recording),
            "imported_at_utc": datetime.now(timezone.utc).isoformat(),
            "duckdb_tables": [table["name"] for table in inspection["tables"]],
            "duckdb_version": inspection.get("duckdb_version"),
        }

        result = finalizer.finalize(
            samples,
            started_at=started_at,
            ended_at=ended_at,
            sim=LMU_SIM_NAME,
            track=samples[0].track_name,
            session_type=samples[0].session_type,
            session_uid=f"lmu-{uuid.uuid4().hex[:12]}",
            extra_metadata=extra_metadata,
            laps=lap_records,
            events=_build_import_events(inspection, telemetry.event_rows, started_at),
            driver_name=(metadata.get("driver_name") or config.driver_name or None),
            adapter_name="LMURecordingImport",
            raw_capture_sim=LMU_RAW_SIM_NAME,
            raw_samples=telemetry.raw_rows,
            raw_columns=telemetry.raw_columns,
            raw_session_info=inspection,
        )
        if result is None:
            raise LMUImportError("LMU recording import finalized without producing a bundle")

        _attach_lmu_artifacts(result, recording, inspection)
        return result
    finally:
        _close_connection(conn)


def inspect_lmu_recording(
    recording_path: str | Path,
    *,
    conn: Any | None = None,
) -> dict[str, Any]:
    """Inspect table names, columns, and sample rows for one LMU recording."""
    recording = Path(recording_path)
    own_connection = False
    if conn is None:
        duckdb = _load_duckdb_module()
        conn = _connect_read_only(duckdb, recording)
        own_connection = True

    try:
        tables = _query_scalar_rows(conn, "SHOW TABLES")
        table_names = [next(iter(row.values())) for row in tables]
        summaries = []
        for table_name in table_names:
            columns = _describe_table(conn, table_name)
            row_count = _query_single_value(conn, f'SELECT COUNT(*) AS row_count FROM "{table_name}"')
            sample_rows = _query_rows(conn, f'SELECT * FROM "{table_name}" LIMIT 3')
            summaries.append(
                TableSummary(
                    name=str(table_name),
                    columns=columns,
                    row_count=int(row_count or 0),
                    sample_rows=sample_rows,
                )
            )

        return {
            "recording_path": str(recording),
            "duckdb_version": _query_single_value(conn, "SELECT version() AS version"),
            "inspected_at_utc": datetime.now(timezone.utc).isoformat(),
            "tables": [
                {
                    "name": summary.name,
                    "columns": summary.columns,
                    "row_count": summary.row_count,
                    "sample_rows": summary.sample_rows,
                }
                for summary in summaries
            ],
        }
    finally:
        if own_connection:
            _close_connection(conn)


@dataclass
class _TelemetryLoadResult:
    normalized_rows: list[dict[str, Any]]
    raw_rows: list[dict[str, Any]]
    raw_columns: list[str]
    event_rows: list[dict[str, Any]]


def _load_telemetry_rows(conn: Any, inspection: dict[str, Any]) -> _TelemetryLoadResult:
    summaries = [
        TableSummary(
            name=table["name"],
            columns=list(table.get("columns") or []),
            row_count=int(table.get("row_count") or 0),
            sample_rows=list(table.get("sample_rows") or []),
        )
        for table in inspection["tables"]
    ]

    long_table = _pick_long_telemetry_table(summaries)
    if long_table is not None:
        time_col, name_col, value_col = long_table
        rows = _query_rows(
            conn,
            f'SELECT * FROM "{time_col.table}"',
        )
        normalized_rows = _pivot_long_rows(rows, time_key=time_col.column, name_key=name_col.column, value_key=value_col.column)
        raw_rows = [
            {
                "lmu__source_table": time_col.table,
                "lmu__sample_time": row.get(time_col.column),
                "lmu__channel_name": row.get(name_col.column),
                "lmu__value": row.get(value_col.column),
            }
            for row in rows
        ]
        event_rows = _load_event_rows(conn, summaries)
        return _TelemetryLoadResult(
            normalized_rows=normalized_rows,
            raw_rows=raw_rows,
            raw_columns=["lmu__channel_name", "lmu__sample_time", "lmu__source_table", "lmu__value"],
            event_rows=event_rows,
        )

    wide_table = _pick_wide_telemetry_table(summaries)
    if wide_table is not None:
        rows = _query_rows(conn, f'SELECT * FROM "{wide_table.name}"')
        normalized_rows = _normalize_wide_rows(rows)
        raw_rows = [_prefix_row("lmu", row) for row in rows]
        raw_columns = sorted(raw_rows[0].keys()) if raw_rows else []
        event_rows = _load_event_rows(conn, summaries)
        return _TelemetryLoadResult(
            normalized_rows=normalized_rows,
            raw_rows=raw_rows,
            raw_columns=raw_columns,
            event_rows=event_rows,
        )

    raise LMUImportError("Could not identify a supported LMU telemetry table in the DuckDB recording")


@dataclass(frozen=True)
class _TableColumnRef:
    table: str
    column: str


def _pick_long_telemetry_table(
    summaries: list[TableSummary],
) -> tuple[_TableColumnRef, _TableColumnRef, _TableColumnRef] | None:
    for summary in sorted(summaries, key=lambda item: _table_priority(item.name)):
        cols = { _normalize_name(name): name for name in summary.columns }
        time_col = next((cols[key] for key in _TIME_COLUMN_CANDIDATES if key in cols), None)
        name_col = next((cols[key] for key in _NAME_COLUMN_CANDIDATES if key in cols), None)
        value_col = next((cols[key] for key in _VALUE_COLUMN_CANDIDATES if key in cols), None)
        if time_col and name_col and value_col:
            return (
                _TableColumnRef(summary.name, time_col),
                _TableColumnRef(summary.name, name_col),
                _TableColumnRef(summary.name, value_col),
            )
    return None


def _pick_wide_telemetry_table(summaries: list[TableSummary]) -> TableSummary | None:
    for summary in sorted(summaries, key=lambda item: _table_priority(item.name)):
        normalized = {_normalize_name(name) for name in summary.columns}
        if not normalized.intersection(_TIME_COLUMN_CANDIDATES):
            continue
        channel_hits = sum(1 for name in normalized if name in _LMU_CHANNEL_ALIASES)
        if channel_hits >= 3:
            return summary
    return None


def _load_event_rows(conn: Any, summaries: list[TableSummary]) -> list[dict[str, Any]]:
    for summary in sorted(summaries, key=lambda item: _table_priority(item.name)):
        cols = {_normalize_name(name): name for name in summary.columns}
        time_col = next((cols[key] for key in _TIME_COLUMN_CANDIDATES if key in cols), None)
        event_col = next((cols[key] for key in _EVENT_COLUMN_CANDIDATES if key in cols), None)
        if time_col and event_col and "event" in _normalize_name(summary.name):
            return _query_rows(conn, f'SELECT * FROM "{summary.name}"')
    return []


def _pivot_long_rows(
    rows: list[dict[str, Any]],
    *,
    time_key: str,
    name_key: str,
    value_key: str,
) -> list[dict[str, Any]]:
    grouped: "OrderedDict[float, dict[str, Any]]" = OrderedDict()
    for row in rows:
        sample_time = _coerce_time_seconds(row.get(time_key))
        if sample_time is None:
            continue
        channel_name = _canonical_channel_name(row.get(name_key))
        if channel_name is None:
            continue
        bucket = round(sample_time, 6)
        target = grouped.setdefault(bucket, {"GPS Time": sample_time})
        target[channel_name] = row.get(value_key)
    return list(grouped.values())


def _normalize_wide_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        mapped: dict[str, Any] = {}
        for key, value in row.items():
            normalized_name = _canonical_channel_name(key)
            if normalized_name is None:
                if _normalize_name(key) in _TIME_COLUMN_CANDIDATES:
                    normalized_name = "GPS Time"
                else:
                    continue
            mapped[normalized_name] = value
        if mapped:
            normalized_rows.append(mapped)
    return normalized_rows


def _build_samples_from_rows(
    rows: list[dict[str, Any]],
    *,
    recording: Path,
    metadata: dict[str, Any],
) -> list[TelemetrySample]:
    ordered = sorted(
        rows,
        key=lambda row: (_coerce_time_seconds(row.get("GPS Time")) or 0.0),
    )
    time_values = [_coerce_time_seconds(row.get("GPS Time")) for row in ordered]
    non_null_times = [value for value in time_values if value is not None]
    if non_null_times:
        end_time = datetime.fromtimestamp(recording.stat().st_mtime, tz=timezone.utc)
        start_time = end_time - timedelta(seconds=max(non_null_times))
    else:
        start_time = datetime.fromtimestamp(recording.stat().st_mtime, tz=timezone.utc)

    samples: list[TelemetrySample] = []
    for idx, row in enumerate(ordered):
        session_time = _coerce_time_seconds(row.get("GPS Time"))
        if session_time is None:
            session_time = float(idx)
            row = dict(row)
            row["GPS Time"] = session_time
        timestamp = (start_time + timedelta(seconds=session_time)).isoformat()
        sample = normalise_sample(
            row,
            sim=LMU_SIM_NAME,
            passthrough={
                "timestamp_utc": timestamp,
                "track_name": metadata.get("track_name"),
                "car_name": metadata.get("car_name"),
                "session_type": metadata.get("session_type"),
            },
        )
        samples.append(sample)
    return samples


def _build_import_events(
    inspection: dict[str, Any],
    event_rows: list[dict[str, Any]],
    started_at: datetime,
) -> list[SessionEvent]:
    events = [
        SessionEvent(
            event="lmu_import_started",
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            detail={"recording_path": inspection["recording_path"]},
        )
    ]
    for row in event_rows:
        event_name = None
        event_time = None
        detail: dict[str, Any] = {}
        for key, value in row.items():
            normalized = _normalize_name(key)
            if normalized in _EVENT_COLUMN_CANDIDATES and value is not None:
                event_name = str(value)
            elif normalized in _TIME_COLUMN_CANDIDATES:
                event_time = _coerce_time_seconds(value)
            else:
                detail[key] = value
        if not event_name:
            continue
        timestamp = (
            (started_at + timedelta(seconds=event_time)).isoformat()
            if event_time is not None
            else datetime.now(timezone.utc).isoformat()
        )
        events.append(
            SessionEvent(
                event=f"lmu_{_slugify(event_name)}",
                timestamp_utc=timestamp,
                detail=detail or None,
            )
        )
    return events


def _attach_lmu_artifacts(bundle_dir: Path, recording: Path, inspection: dict[str, Any]) -> None:
    raw_db_name = "telemetry_lmu_raw.duckdb"
    inspection_name = "lmu_recording_inspection.json"
    shutil.copy2(recording, bundle_dir / raw_db_name)
    (bundle_dir / inspection_name).write_text(json.dumps(inspection, indent=2), encoding="utf-8")

    session_path = bundle_dir / "session.json"
    session = json.loads(session_path.read_text(encoding="utf-8"))

    source_meta = dict(session.get("source_metadata") or {})
    raw_capture = dict(source_meta.get("raw_capture") or {})
    raw_capture["sim"] = LMU_SIM_NAME
    raw_files = dict(source_meta.get("lmu_raw_files") or {})
    raw_files["telemetry_lmu_raw_duckdb"] = raw_db_name
    raw_files["lmu_recording_inspection"] = inspection_name
    raw_capture["files"] = {**dict(raw_capture.get("files") or {}), **raw_files}
    source_meta["raw_capture"] = raw_capture
    source_meta["lmu_raw_files"] = raw_files
    source_meta["import_source"] = "lmu_duckdb"

    session["source_metadata"] = source_meta
    session_path.write_text(json.dumps(session, indent=2), encoding="utf-8")


def _extract_metadata(inspection: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for table in inspection["tables"]:
        table_name = _normalize_name(table["name"])
        for row in table.get("sample_rows") or []:
            for key, value in row.items():
                alias = _METADATA_KEY_ALIASES.get(_normalize_name(key))
                if alias and alias not in result and value not in (None, ""):
                    result[alias] = value
            if {"track_name", "car_name", "session_type"}.issubset(result.keys()):
                return result
        if "metadata" in table_name or "session" in table_name or "info" in table_name:
            continue
    return result


def _query_rows(conn: Any, query: str) -> list[dict[str, Any]]:
    cursor = conn.execute(query)
    columns = [desc[0] for desc in (cursor.description or [])]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _query_scalar_rows(conn: Any, query: str) -> list[dict[str, Any]]:
    return _query_rows(conn, query)


def _query_single_value(conn: Any, query: str) -> Any:
    rows = _query_rows(conn, query)
    if not rows:
        return None
    return next(iter(rows[0].values()))


def _describe_table(conn: Any, table_name: str) -> list[str]:
    cursor = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 0')
    return [desc[0] for desc in (cursor.description or [])]


def _connect_read_only(duckdb: types.ModuleType, recording: Path) -> Any:
    try:
        return duckdb.connect(str(recording), read_only=True)
    except TypeError:
        return duckdb.connect(str(recording))


def _close_connection(conn: Any) -> None:
    try:
        conn.close()
    except Exception:
        pass


def _load_duckdb_module() -> types.ModuleType:
    try:
        module = import_module("duckdb")
    except ImportError as exc:
        raise LMUImportError(
            "LMU import requires the optional 'duckdb' package. Install with: pip install duckdb"
        ) from exc
    return module


def _canonical_channel_name(value: Any) -> str | None:
    if value is None:
        return None
    normalized = _normalize_name(str(value))
    return _LMU_CHANNEL_ALIASES.get(normalized)


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _coerce_time_seconds(value: Any) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)
    except Exception:
        return None
    if parsed < 0:
        return None
    if parsed > 1_000_000:
        return parsed / 1000.0
    return parsed


def _estimate_sample_rate_hz(samples: list[TelemetrySample]) -> float | None:
    times = [sample.session_time_s for sample in samples if sample.session_time_s is not None]
    if len(times) < 2:
        return None
    deltas = [b - a for a, b in zip(times, times[1:]) if b > a]
    if not deltas:
        return None
    average = sum(deltas) / len(deltas)
    return round(1.0 / average, 2) if average > 0 else None


def _prefix_row(prefix: str, row: dict[str, Any]) -> dict[str, Any]:
    return {f"{prefix}__{_slugify(key)}": value for key, value in row.items()}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(value)).strip("_").lower()
    return slug or "value"


def _table_priority(name: str) -> tuple[int, str]:
    normalized = _normalize_name(name)
    if "telemetry" in normalized or "channel" in normalized or "sample" in normalized:
        return (0, normalized)
    if "event" in normalized:
        return (1, normalized)
    if "metadata" in normalized or "session" in normalized:
        return (2, normalized)
    return (3, normalized)


def print_lmu_import_result(bundle_dir: Path) -> None:
    """Helper for CLI output."""
    sys.stdout.write(f"{bundle_dir}\n")
