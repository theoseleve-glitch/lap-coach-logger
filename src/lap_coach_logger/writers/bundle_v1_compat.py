"""Backward compat shim: read v1 bundle, produce v2 SessionManifest (T038).

The reprocess pipeline can hand a legacy v1 bundle directory to
``load_v1_bundle_as_manifest`` and receive a populated
``lap_schemas.v1.SessionManifest`` — suitable for feeding through
``SessionFinalizer.finalize(manifest=...)`` to re-emit the session
in Bundle v2 format.

Fields the v1 bundle doesn't carry — UUID7 ids for driver / car /
track / session, plus DataQuality + SensorConfigSnapshot — are
synthesised with reasonable defaults. The resulting manifest validates
against the shared v2 contract but callers should replace the
synthetic UUIDs with real ones before uploading to ingestion.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import uuid6

from lap_schemas.v1 import SessionManifest
from lap_schemas.v1.data_quality import DataQuality
from lap_schemas.v1.environment import EnvironmentTag
from lap_schemas.v1.sensor_config import SensorConfig, SensorConfigSnapshot


_LEGACY_SESSION_JSON = "session.json"


def load_v1_bundle_as_manifest(bundle_dir: Path) -> SessionManifest:
    """Read a v1 bundle directory and return an equivalent v2 SessionManifest."""
    session_path = bundle_dir / _LEGACY_SESSION_JSON
    if not session_path.exists():
        raise FileNotFoundError(
            f"v1 bundle missing session.json: {bundle_dir}"
        )

    data: dict[str, Any] = json.loads(session_path.read_text(encoding="utf-8"))

    started_at = _parse_timestamp(data.get("started_at_utc")) or _utcnow()
    ended_at = _parse_timestamp(data.get("ended_at_utc")) or started_at
    duration_seconds = max(0.0, (ended_at - started_at).total_seconds())
    total_samples = int(data.get("sample_count") or 0)
    sample_rate_hz = float(data.get("sample_rate_hz") or 1.0) or 1.0

    sim = str(data.get("sim_name") or "unknown")

    return SessionManifest(
        session_id=uuid6.uuid7(),
        driver_id=uuid6.uuid7(),
        bundle_version="v2",
        capture_app="lap-coach-logger",
        capture_app_version=str(data.get("logger_version") or "0.0.0"),
        device_model="Desktop",
        device_os="Windows",
        device_os_version="",
        source=sim,
        sim_title=sim or None,
        real_hardware=None,
        car_id=uuid6.uuid7(),
        track_id=uuid6.uuid7(),
        track_layout=str(data.get("track_name") or "unknown"),
        environment_tag=EnvironmentTag.SIM_PRACTICE,
        objective_tag=None,
        training_block_id=None,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        telemetry_checksums={},
        total_samples=total_samples,
        sample_rate_hz=sample_rate_hz,
        data_quality=_default_data_quality(),
        sensor_config=_default_sensor_config(sim, sample_rate_hz),
    )


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _default_data_quality() -> DataQuality:
    return DataQuality(
        score=0.0,
        channel_completeness=0.0,
        sample_gaps_count=0,
        sample_rate_stability=0.0,
        warnings=("reprocessed_from_v1_bundle",),
        recommendations=(),
        usable_for_overlays=False,
        usable_for_long_term_coaching=False,
    )


def _default_sensor_config(sim: str, sample_rate_hz: float) -> SensorConfigSnapshot:
    # Use a reasonable sample_rate default when the v1 bundle didn't record one.
    safe_rate = sample_rate_hz if sample_rate_hz > 0 else 1.0
    return SensorConfigSnapshot(
        sensors=(SensorConfig(name=sim or "legacy", sample_rate_hz=safe_rate),),
    )


__all__ = ["load_v1_bundle_as_manifest"]
