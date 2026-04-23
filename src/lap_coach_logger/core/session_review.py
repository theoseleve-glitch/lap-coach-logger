"""Saved-session review helpers for offline review and reprocessing."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from lap_coach_logger.config.models import AppConfig
from lap_coach_logger.core.lap_analysis import classify_laps
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.session_quality import validate_session_quality
from lap_coach_logger.core.sync_queue import SyncQueueManager
from lap_coach_logger.core.sync_status import (
    SYNC_STATUS_NOT_QUEUED,
    derive_sync_status,
    is_sync_ready,
)
from lap_coach_logger.writers.bundle_schema import compute_file_sha256

REVIEW_STATUS_READY = "ready"
REVIEW_STATUS_IGNORED = "ignored"

_STRING_FIELDS = {
    "timestamp_utc",
    "sim",
    "session_uid",
    "track_name",
    "car_name",
    "session_type",
}
_INT_FIELDS = {"lap_number", "gear"}
_BOOL_FIELDS = {"is_on_track", "is_in_pits"}
_FLOAT_FIELDS = set(TelemetrySample.field_names()) - _STRING_FIELDS - _INT_FIELDS - _BOOL_FIELDS


def _v2_get(manifest: dict[str, Any], *paths: str, default: Any = None) -> Any:
    """Read from v2 nested paths or v1 flat fields, returning first non-None."""
    for p in paths:
        parts = p.split(".")
        val = manifest
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                val = None
                break
        if val is not None:
            return val
    return default


def load_session_review(folder: str | Path) -> dict[str, Any]:
    path = Path(folder)
    manifest = _read_json(path / "session.json")
    quality = _read_json(path / "quality_report.json")
    analysis = _read_json(path / "analysis.json")

    # v2 nested accessors with v1 flat-field fallbacks
    raw_source = manifest.get("raw_source") or {}
    session_block = manifest.get("session") or {}
    readiness = manifest.get("analysis_readiness") or {}

    review_status = manifest.get("review_status") or REVIEW_STATUS_READY

    warnings = _coerce_str_list(quality.get("warnings"))
    errors = _coerce_str_list(quality.get("rejection_reasons"))

    quality_class = (
        quality.get("recommended_classification")
        or manifest.get("quality_classification")
        or "-"
    )
    if quality_class == "-" and readiness:
        verdict = (analysis.get("recommendation") or {}).get("verdict")
        if verdict == "recommended":
            quality_class = "accepted"
        elif verdict == "conditional":
            quality_class = "accepted_with_warnings"
        elif verdict == "not_recommended":
            quality_class = "rejected"

    return {
        "name": path.name,
        "folder": str(path),
        "session_id": manifest.get("session_id") or session_block.get("session_uid") or path.name,
        "created_at": (
            session_block.get("start_time")
            or manifest.get("started_at_utc")
        ),
        "schema_version": manifest.get("schema_version") or "",
        "session_status": _display_review_status(review_status),
        "review_status": review_status,
        "review_updated_at_utc": manifest.get("review_updated_at_utc"),
        "quality_classification": quality_class,
        "quality_score": (
            readiness.get("quality_score")
            or manifest.get("quality_score")
        ),
        "simulator": (
            raw_source.get("sim_display_name")
            or raw_source.get("sim_id")
            or manifest.get("sim_name")
            or "-"
        ),
        "track": (
            raw_source.get("raw_track")
            or manifest.get("track_name")
            or "-"
        ),
        "car": (
            raw_source.get("raw_car")
            or manifest.get("car_name")
            or "-"
        ),
        "session_type": (
            raw_source.get("session_type_raw")
            or manifest.get("session_type")
            or "-"
        ),
        "duration_s": session_block.get("duration_s") or manifest.get("duration_s") or 0,
        "sample_count": session_block.get("sample_count") or manifest.get("sample_count") or 0,
        "total_laps": (
            session_block.get("lap_count")
            or manifest.get("total_laps")
            or 0
        ),
        "valid_laps": manifest.get("valid_laps") or 0,
        "clean_laps": manifest.get("clean_laps") or 0,
        "best_lap_time_s": manifest.get("best_lap_time_s"),
        "best_clean_lap_time_s": manifest.get("best_clean_lap_time_s"),
        "warnings": warnings,
        "errors": errors,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "sync_status": manifest.get("sync_status") or SYNC_STATUS_NOT_QUEUED,
        "sync_attempt_count": int(manifest.get("sync_attempt_count") or 0),
        "last_sync_attempt_at": manifest.get("last_sync_attempt_at"),
        "last_sync_error": manifest.get("last_sync_error"),
        "bundle_hash": manifest.get("bundle_hash"),
        "remote_id": manifest.get("remote_id"),
        "sync_ready": is_sync_ready(
            review_status=review_status,
            quality_classification=quality_class,
        ),
        "local_folder_path": str(path),
        "ended_at_utc": (
            session_block.get("end_time")
            or manifest.get("ended_at_utc")
        ),
    }


def load_history_entry(folder: str | Path) -> dict[str, Any]:
    """Load enhanced history entry with all fields needed for archival display and filtering."""
    review = load_session_review(folder)
    ended = review.get("ended_at_utc")
    if isinstance(ended, str) and ended:
        ended_dt = datetime.fromisoformat(ended.replace("Z", "+00:00"))
        ended_display = ended_dt.strftime("%Y-%m-%d %H:%M")
        ended_date = ended_dt.strftime("%Y-%m-%d")
    else:
        ended_dt = datetime.fromtimestamp(Path(folder).stat().st_mtime)
        ended_display = ended_dt.strftime("%Y-%m-%d %H:%M")
        ended_date = ended_dt.strftime("%Y-%m-%d")

    best_clean = review.get("best_clean_lap_time_s")
    best_lap = review.get("best_lap_time_s")
    duration = review.get("duration_s", 0)
    
    return {
        # Identity
        "folder": review["folder"],
        "name": review["name"],
        "session_id": str(review.get("session_id") or Path(review["folder"]).name),
        "created_at": review.get("created_at"),
        "schema_version": review.get("schema_version") or "",
        
        # Metadata
        "sim": review["simulator"],
        "track": review["track"],
        "car": review["car"],
        "session_type": review["session_type"],
        
        # Quality
        "quality": review["quality_classification"],
        "quality_score": review.get("quality_score"),
        "warning_count": review.get("warning_count", 0),
        "error_count": review.get("error_count", 0),
        
        # Lap data
        "total_laps": review.get("total_laps", 0),
        "valid_laps": review.get("valid_laps", 0),
        "clean_laps": review.get("clean_laps", 0),
        "best_lap": f"{best_lap:.3f}s" if isinstance(best_lap, (int, float)) else "-",
        "best_lap_s": float(best_lap) if isinstance(best_lap, (int, float)) else None,
        "best_clean_lap": f"{best_clean:.3f}s" if isinstance(best_clean, (int, float)) else "-",
        
        # Telemetry data
        "sample_count": review["sample_count"],
        "duration_s": duration,
        "duration_display": _format_duration_archive(duration),
        
        # Time/Status
        "ended": ended_display,
        "ended_display": ended_display,
        "ended_date": ended_date,
        "ended_at_utc": review.get("ended_at_utc"),
        "review_status": review["review_status"],
        "sync_status": review.get("sync_status") or SYNC_STATUS_NOT_QUEUED,
        "bundle_hash": review.get("bundle_hash") or "",
        "sync_ready": bool(review.get("sync_ready")),
        "analysis_ready": review["quality_classification"] and review["quality_classification"] != "-",
    }


def _format_duration_archive(duration_s: float) -> str:
    """Format duration for display in archive (e.g., '1h 23m 45s' or '5m 12s')."""
    if not isinstance(duration_s, (int, float)) or duration_s <= 0:
        return "—"
    total_seconds = int(duration_s)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s"


def set_session_review_status(folder: str | Path, review_status: str) -> dict[str, Any]:
    path = Path(folder)
    manifest_path = path / "session.json"
    manifest = _read_json(manifest_path)
    updated_at = datetime.now(timezone.utc).isoformat()

    manifest["review_status"] = review_status
    manifest["review_updated_at_utc"] = updated_at

    readiness = manifest.get("analysis_readiness") or {}
    quality_class = manifest.get("quality_classification") or (
        "accepted" if readiness.get("ready_for_analysis") else "rejected"
    )
    sync_status = derive_sync_status(
        current_status=manifest.get("sync_status"),
        review_status=review_status,
        quality_classification=quality_class,
        remote_id=manifest.get("remote_id"),
    )
    manifest["sync_status"] = sync_status

    _write_json(manifest_path, manifest)
    return load_session_review(path)


def reprocess_session_bundle(folder: str | Path, *, config: AppConfig) -> dict[str, Any]:
    path = Path(folder)
    manifest_path = path / "session.json"
    quality_path = path / "quality_report.json"
    laps_path = path / "laps.json"

    manifest = _read_json(manifest_path)
    raw_source = manifest.get("raw_source") or {}
    session_block = manifest.get("session") or {}
    samples, telemetry_file = _load_saved_samples(path, manifest)

    session_id = str(manifest.get("session_id") or session_block.get("session_uid") or path.name)
    existing_remote_id = manifest.get("remote_id")

    track_name = raw_source.get("raw_track") or manifest.get("track_name")
    car_name = raw_source.get("raw_car") or manifest.get("car_name")
    session_type = raw_source.get("session_type_raw") or manifest.get("session_type")

    lap_records, lap_summary = classify_laps(samples, config=config.lap_analysis)
    quality_report = validate_session_quality(
        samples=samples,
        laps=lap_records,
        track_name=track_name,
        car_name=car_name,
        session_type=session_type,
        sample_rate_hz=manifest.get("sample_rate_hz"),
        config=config.quality,
    )

    laps_path.write_text(
        json.dumps([lap.to_dict() for lap in lap_records], indent=2),
        encoding="utf-8",
    )
    quality_path.write_text(json.dumps(quality_report.to_dict(), indent=2), encoding="utf-8")

    review_status = manifest.get("review_status") or REVIEW_STATUS_READY
    review_updated_at = datetime.now(timezone.utc).isoformat()
    bundle_hash = SyncQueueManager.compute_bundle_hash(
        session_id=session_id,
        telemetry_sha256=compute_file_sha256(telemetry_file),
    )
    sync_status = derive_sync_status(
        current_status=manifest.get("sync_status"),
        review_status=review_status,
        quality_classification=quality_report.recommended_classification,
        remote_id=existing_remote_id,
    )

    manifest.update(
        {
            "total_laps": lap_summary.total_laps,
            "valid_laps": lap_summary.valid_laps,
            "clean_laps": lap_summary.clean_laps,
            "best_lap_time_s": lap_summary.best_lap_time_s,
            "best_clean_lap_time_s": lap_summary.best_clean_lap_time_s,
            "representative_lap_number": lap_summary.representative_lap_number,
            "representative_lap_time_s": lap_summary.representative_lap_time_s,
            "quality_classification": quality_report.recommended_classification,
            "quality_score": quality_report.overall_quality_score,
            "quality_report_file": "quality_report.json",
            "review_status": review_status,
            "review_updated_at_utc": review_updated_at,
            "sync_status": sync_status,
            "sync_attempt_count": int(manifest.get("sync_attempt_count") or 0),
            "last_sync_attempt_at": manifest.get("last_sync_attempt_at"),
            "last_sync_error": manifest.get("last_sync_error"),
            "bundle_hash": bundle_hash,
            "remote_id": existing_remote_id,
        }
    )

    _write_json(manifest_path, manifest)
    return load_session_review(path)


def _compute_data_quality(samples: list[TelemetrySample]) -> float:
    critical = ("speed_kph", "throttle_pct", "brake_pct", "gear", "lap_number")
    total = len(samples) * len(critical)
    if total == 0:
        return 0.0
    non_null = sum(1 for sample in samples for field in critical if getattr(sample, field, None) is not None)
    return round(non_null / total, 4)


def _compute_duration(samples: list[TelemetrySample], fallback: float) -> float:
    session_times = [sample.session_time_s for sample in samples if sample.session_time_s is not None]
    if len(session_times) >= 2:
        return max(0.0, float(session_times[-1]) - float(session_times[0]))

    timestamps = []
    for sample in samples:
        try:
            timestamps.append(datetime.fromisoformat(sample.timestamp_utc).timestamp())
        except Exception:
            continue
    if len(timestamps) >= 2:
        return max(0.0, timestamps[-1] - timestamps[0])
    return float(fallback)


def _load_saved_samples(folder: Path, manifest: dict[str, Any]) -> tuple[list[TelemetrySample], Path]:
    telemetry_name = manifest.get("telemetry_file")
    candidates = []
    if telemetry_name:
        candidates.append(folder / str(telemetry_name))
    candidates.extend([folder / "telemetry.csv", folder / "telemetry.parquet"])

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if not candidate.exists():
            continue
        if candidate.suffix.lower() == ".csv":
            return _load_csv_samples(candidate), candidate
        if candidate.suffix.lower() == ".parquet":
            return _load_parquet_samples(candidate), candidate

    raise FileNotFoundError(f"No saved telemetry file found in {folder}")


def _load_csv_samples(path: Path) -> list[TelemetrySample]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [_coerce_sample_row(row) for row in reader]


def _load_parquet_samples(path: Path) -> list[TelemetrySample]:
    table = pq.read_table(path)
    return [_coerce_sample_row(row) for row in table.to_pylist()]


def _coerce_sample_row(row: dict[str, Any]) -> TelemetrySample:
    payload: dict[str, Any] = {}
    for field in TelemetrySample.field_names():
        payload[field] = _coerce_value(field, row.get(field))
    return TelemetrySample(**payload)


def _coerce_value(field: str, value: Any) -> Any:
    if value is None or value == "":
        return None
    if field in _STRING_FIELDS:
        return str(value)
    if field in _INT_FIELDS:
        try:
            return int(float(value))
        except Exception:
            return None
    if field in _BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no"}:
            return False
        return None
    if field in _FLOAT_FIELDS:
        try:
            return float(value)
        except Exception:
            return None
    return value


def _display_review_status(review_status: str) -> str:
    if review_status == REVIEW_STATUS_IGNORED:
        return "Ignored"
    return "Ready for Review"


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")