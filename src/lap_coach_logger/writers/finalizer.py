"""Session finalization orchestrator.

Responsible for:
1. Creating a temp session folder.
2. Writing a structured **session bundle**:
   - ``session.json``  — manifest + metadata
   - ``telemetry.csv`` (primary) or ``telemetry.parquet`` (fallback)
   - ``laps.json``     — per-lap timing records
   - ``events.json``   — lifecycle event log
   - ``channels.json`` — telemetry channel definitions
3. Optionally writing ``telemetry_debug.csv`` when debug export is enabled.
4. Computing SHA-256 checksum of the telemetry file.
5. Atomically renaming the temp folder to the final session folder.
6. Cleaning up stale temp folders from previous crashes on startup.
7. Validating schema consistency before writing.

Backward compatibility: the ``metadata.json`` file is still written
as a thin shim that points to ``session.json`` for any tooling that
relies on the old format.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lap_coach_logger import __version__
from lap_coach_logger.config.models import QualityConfig
from lap_coach_logger.core.schema import TELEMETRY_SCHEMA_VERSION, TelemetrySample
from lap_coach_logger.core.session_quality import validate_session_quality
from lap_coach_logger.core.sync_queue import SyncQueueManager
from lap_coach_logger.writers.bundle_schema import (
    BUNDLE_SCHEMA_VERSION,
    ChannelDef,
    LapRecord,
    SessionEvent,
    SessionManifest,
    compute_file_sha256,
)
from lap_coach_logger.writers.channels import build_channels_payload, build_raw_iracing_channels_payload
from lap_coach_logger.writers.csv_writer import CsvWriter
from lap_coach_logger.writers.parquet_writer import ParquetWriter

log = logging.getLogger(__name__)

_TEMP_PREFIX = "_tmp_"


# ------------------------------------------------------------------
# Folder naming
# ------------------------------------------------------------------

def _safe_slug(text: str | None, fallback: str = "unknown") -> str:
    if not text:
        return fallback
    # Replace any non-alphanumeric/dash/underscore with underscore
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", text.strip())
    # Collapse runs of underscores
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:40] or fallback


def session_folder_name(
    started_at: datetime,
    sim: str | None,
    track: str | None,
    session_type: str | None,
) -> str:
    """Build a deterministic, filesystem-safe folder name."""
    ts = started_at.strftime("%Y-%m-%d_%H-%M-%S")
    parts = [ts, _safe_slug(sim), _safe_slug(track), _safe_slug(session_type)]
    return "__".join(parts)


def _validate_samples(samples: list[TelemetrySample]) -> list[str]:
    """Return a list of schema-consistency warnings (empty = ok)."""
    warnings: list[str] = []
    if not samples:
        warnings.append("No samples to write")
        return warnings

    expected_fields = set(TelemetrySample.field_names())
    actual_fields = set(samples[0].to_dict().keys())
    extra = actual_fields - expected_fields
    missing = expected_fields - actual_fields
    if extra:
        warnings.append(f"Unexpected fields: {extra}")
    if missing:
        warnings.append(f"Missing fields: {missing}")
    return warnings


def _compute_data_quality(samples: list[TelemetrySample]) -> float:
    """Return fraction of non-null values across critical channels."""
    critical = ("speed_kph", "throttle_pct", "brake_pct", "gear", "lap_number")
    total = len(samples) * len(critical)
    if total == 0:
        return 0.0
    non_null = sum(
        1 for s in samples for f in critical if getattr(s, f, None) is not None
    )
    return round(non_null / total, 4)


# ------------------------------------------------------------------
# Finalizer
# ------------------------------------------------------------------

class SessionFinalizer:
    """Writes a completed session bundle to disk."""

    def __init__(
        self,
        output_root: Path,
        *,
        compression: str = "snappy",
        debug_csv_export: bool = False,
        quality_config: QualityConfig | None = None,
    ) -> None:
        self._output_root = output_root
        self._compression = compression
        self._debug_csv_export = debug_csv_export
        self._quality_config = quality_config or QualityConfig()

    # ------------------------------------------------------------------
    def finalize(
        self,
        samples: list[TelemetrySample],
        *,
        started_at: datetime,
        ended_at: datetime | None = None,
        sim: str | None = None,
        track: str | None = None,
        session_type: str | None = None,
        session_uid: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
        laps: list[LapRecord] | None = None,
        events: list[SessionEvent] | None = None,
        driver_name: str | None = None,
        adapter_name: str | None = None,
        iracing_raw_samples: list[dict[str, Any]] | None = None,
        iracing_raw_columns: list[str] | None = None,
        iracing_session_info: dict[str, Any] | None = None,
        iracing_catalogs: dict[str, Any] | None = None,
        iracing_var_schema: list[dict[str, Any]] | None = None,
    ) -> Path | None:
        """Write session bundle and return the final folder path (or None on total failure)."""
        ended_at = ended_at or datetime.now(timezone.utc)
        duration_s = (ended_at - started_at).total_seconds()

        # Schema validation
        schema_warnings = _validate_samples(samples)
        for w in schema_warnings:
            log.warning("Schema check: %s", w)

        folder_name = session_folder_name(started_at, sim, track, session_type)
        tmp_dir = self._output_root / f"{_TEMP_PREFIX}{folder_name}"
        final_dir = self._output_root / folder_name

        extra = dict(extra_metadata) if extra_metadata else {}

        try:
            self._output_root.mkdir(parents=True, exist_ok=True)
            tmp_dir.mkdir(parents=True, exist_ok=True)

            # ── telemetry data ──
            write_format = self._write_telemetry(tmp_dir, samples)

            # ── optional debug CSV export ──
            if self._debug_csv_export and write_format == "parquet":
                self._write_debug_csv(tmp_dir, samples)

            # ── telemetry checksum ──
            tel_filename = f"telemetry.{write_format}" if write_format != "none" else None
            tel_sha256: str | None = None
            if tel_filename and (tmp_dir / tel_filename).exists():
                tel_sha256 = compute_file_sha256(tmp_dir / tel_filename)
            sync_bundle_hash = SyncQueueManager.compute_bundle_hash(
                session_id=session_uid or folder_name,
                telemetry_sha256=tel_sha256,
            )

            # ── channels.json ──
            self._write_channels(tmp_dir)

            # ── iRacing raw telemetry outputs ──
            iracing_files: dict[str, str] = {}
            if iracing_raw_samples:
                raw_file = self._write_iracing_raw_telemetry(
                    tmp_dir, iracing_raw_samples, iracing_raw_columns,
                )
                if raw_file:
                    iracing_files["telemetry_iracing_raw"] = raw_file
                # channels_iracing_raw.json
                cols = iracing_raw_columns or (sorted(iracing_raw_samples[0].keys()) if iracing_raw_samples else [])
                self._write_iracing_raw_channels(tmp_dir, cols, iracing_var_schema)
                iracing_files["channels_iracing_raw"] = "channels_iracing_raw.json"

            if iracing_session_info is not None:
                (tmp_dir / "session_info_iracing.json").write_text(
                    json.dumps(iracing_session_info, indent=2, default=str),
                    encoding="utf-8",
                )
                iracing_files["session_info_iracing"] = "session_info_iracing.json"

            if iracing_catalogs is not None:
                (tmp_dir / "iracing_catalogs.json").write_text(
                    json.dumps(iracing_catalogs, indent=2, default=str),
                    encoding="utf-8",
                )
                iracing_files["iracing_catalogs"] = "iracing_catalogs.json"

            # ── laps.json ──
            self._write_laps(tmp_dir, laps or [])

            # ── events.json ──
            self._write_events(tmp_dir, events or [])

            # ── quality_report.json ──
            quality_report = validate_session_quality(
                samples=samples,
                laps=laps or [],
                track_name=track,
                car_name=extra.get("car"),
                session_type=session_type,
                sample_rate_hz=extra.get("sample_rate_hz"),
                config=self._quality_config,
            )
            self._write_quality_report(tmp_dir, quality_report.to_dict())

            # ── session.json (manifest) ──
            data_quality = _compute_data_quality(samples)

            # Inject iRacing file references into source_metadata
            if iracing_files:
                extra["iracing_raw_files"] = iracing_files
                if iracing_raw_samples:
                    extra["iracing_raw_sample_count"] = len(iracing_raw_samples)

            manifest = SessionManifest(
                session_id=session_uid or folder_name,
                schema_version=BUNDLE_SCHEMA_VERSION,
                logger_version=__version__,
                telemetry_schema_version=TELEMETRY_SCHEMA_VERSION,
                adapter=adapter_name or extra.pop("adapter", None),
                sim_name=sim,
                started_at_utc=started_at.isoformat(),
                ended_at_utc=ended_at.isoformat(),
                session_type=session_type,
                track_name=track,
                car_name=extra.pop("car", None),
                driver_name=driver_name,
                sample_count=len(samples),
                dropped_sample_count=extra.pop("dropped_samples", 0),
                sample_rate_hz=extra.pop("sample_rate_hz", None),
                duration_s=round(duration_s, 2),
                data_quality_score=data_quality,
                track_temp_c=extra.pop("track_temp_c", None),
                air_temp_c=extra.pop("air_temp_c", None),
                total_laps=extra.pop("total_laps", 0),
                valid_laps=extra.pop("valid_laps", 0),
                clean_laps=extra.pop("clean_laps", 0),
                best_lap_time_s=extra.pop("best_lap_time_s", None),
                best_clean_lap_time_s=extra.pop("best_clean_lap_time_s", None),
                representative_lap_number=extra.pop("representative_lap_number", None),
                representative_lap_time_s=extra.pop("representative_lap_time_s", None),
                review_status=extra.pop("review_status", "ready"),
                review_updated_at_utc=ended_at.isoformat(),
                sync_status="not_queued",
                sync_attempt_count=0,
                last_sync_attempt_at=None,
                last_sync_error=None,
                bundle_hash=sync_bundle_hash,
                remote_id=None,
                quality_classification=quality_report.recommended_classification,
                quality_score=quality_report.overall_quality_score,
                telemetry_file=tel_filename or "",
                telemetry_format=write_format,
                telemetry_sha256=tel_sha256,
                source_metadata=extra,
            )
            session_path = tmp_dir / "session.json"
            session_path.write_text(
                json.dumps(manifest.to_dict(), indent=2), encoding="utf-8"
            )

            # ── backward-compat metadata.json shim ──
            compat_meta: dict[str, Any] = {
                "app_version": __version__,
                "logger_version": __version__,
                "sim": sim,
                "session_uid": session_uid,
                "track_name": track,
                "car_name": manifest.car_name,
                "session_type": session_type,
                "started_at_utc": started_at.isoformat(),
                "ended_at_utc": ended_at.isoformat(),
                "duration_s": round(duration_s, 2),
                "sample_count": len(samples),
                "dropped_sample_count": manifest.dropped_sample_count,
                "sample_rate_hz": manifest.sample_rate_hz,
                "save_format": write_format,
                "data_quality_score": data_quality,
                "output_path": str(final_dir),
                "schema_warnings": schema_warnings or None,
                "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
                "quality_classification": quality_report.recommended_classification,
                "quality_score": quality_report.overall_quality_score,
                "total_laps": manifest.total_laps,
                "valid_laps": manifest.valid_laps,
                "clean_laps": manifest.clean_laps,
                "best_lap_time_s": manifest.best_lap_time_s,
                "best_clean_lap_time_s": manifest.best_clean_lap_time_s,
                "representative_lap_number": manifest.representative_lap_number,
                "representative_lap_time_s": manifest.representative_lap_time_s,
                "review_status": manifest.review_status,
                "review_updated_at_utc": manifest.review_updated_at_utc,
                "sync_status": manifest.sync_status,
                "sync_attempt_count": manifest.sync_attempt_count,
                "last_sync_attempt_at": manifest.last_sync_attempt_at,
                "last_sync_error": manifest.last_sync_error,
                "bundle_hash": manifest.bundle_hash,
                "remote_id": manifest.remote_id,
                **manifest.source_metadata,
            }
            (tmp_dir / "metadata.json").write_text(
                json.dumps(compat_meta, indent=2), encoding="utf-8"
            )

            # ── atomic rename (shutil.move for Windows safety) ──
            if final_dir.exists():
                # Edge case: duplicate name — append disambiguator
                final_dir = self._output_root / f"{folder_name}_{ended_at.strftime('%f')}"
            shutil.move(str(tmp_dir), str(final_dir))
            log.info("Session bundle finalized → %s", final_dir)
            return final_dir

        except Exception:
            log.exception("Session finalization failed")
            return None

    # ------------------------------------------------------------------
    def _write_telemetry(self, folder: Path, samples: list[TelemetrySample]) -> str:
        """Try CSV first; fall back to Parquet on any error."""
        fields = TelemetrySample.field_names()

        # Primary: CSV
        csv_path = folder / "telemetry.csv"
        csv_w: CsvWriter | None = None
        try:
            csv_w = CsvWriter()
            csv_w.open(csv_path, fields)
            csv_w.write_samples(samples)
            csv_w.close()
            return "csv"
        except Exception:
            log.warning("CSV write failed – falling back to Parquet", exc_info=True)
            # Ensure handle is released before fallback / rename
            if csv_w is not None:
                try:
                    csv_w.close()
                except Exception:
                    pass
            csv_path.unlink(missing_ok=True)

        # Fallback: Parquet
        try:
            writer = ParquetWriter(compression=self._compression)
            writer.open(folder / "telemetry.parquet", fields)
            writer.write_samples(samples)
            writer.close()
            return "parquet"
        except Exception:
            log.exception("Parquet fallback also failed")
            return "none"

    # ------------------------------------------------------------------
    def _write_debug_csv(self, folder: Path, samples: list[TelemetrySample]) -> None:
        """Write an additional CSV alongside the parquet for debugging."""
        try:
            csv_w = CsvWriter()
            csv_w.open(folder / "telemetry_debug.csv", TelemetrySample.field_names())
            csv_w.write_samples(samples)
            csv_w.close()
        except Exception:
            log.warning("Debug CSV export failed", exc_info=True)

    # ------------------------------------------------------------------
    @staticmethod
    def _write_channels(folder: Path) -> None:
        """Write ``channels.json`` from the canonical channel registry."""
        payload = build_channels_payload()
        (folder / "channels.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _write_laps(folder: Path, laps: list[LapRecord]) -> None:
        """Write ``laps.json``."""
        payload = [lap.to_dict() for lap in laps]
        (folder / "laps.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _write_events(folder: Path, events: list[SessionEvent]) -> None:
        """Write ``events.json``."""
        payload = [ev.to_dict() for ev in events]
        (folder / "events.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _write_quality_report(folder: Path, payload: dict[str, Any]) -> None:
        """Write ``quality_report.json`` for ingestion gating."""
        (folder / "quality_report.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    def _write_iracing_raw_telemetry(
        self,
        folder: Path,
        raw_samples: list[dict[str, Any]],
        column_names: list[str] | None,
    ) -> str | None:
        """Write ``telemetry_iracing_raw.csv`` (primary) or ``.parquet`` (fallback).

        Returns the filename written, or None on total failure.
        """
        if not raw_samples:
            return None

        cols = column_names or sorted(raw_samples[0].keys())

        # Primary: CSV
        csv_path = folder / "telemetry_iracing_raw.csv"
        try:
            import csv as csv_mod
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv_mod.DictWriter(f, fieldnames=cols, extrasaction="ignore")
                writer.writeheader()
                for row in raw_samples:
                    writer.writerow({c: row.get(c) for c in cols})
            return "telemetry_iracing_raw.csv"
        except Exception:
            log.warning("iRacing raw CSV write failed – trying Parquet", exc_info=True)
            csv_path.unlink(missing_ok=True)

        # Fallback: Parquet via pyarrow
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            arrays = {}
            for col in cols:
                values = [row.get(col) for row in raw_samples]
                arrays[col] = values
            table = pa.table(arrays)
            pq.write_table(table, folder / "telemetry_iracing_raw.parquet",
                           compression=self._compression)
            return "telemetry_iracing_raw.parquet"
        except Exception:
            log.exception("iRacing raw Parquet write also failed")
            return None

    # ------------------------------------------------------------------
    @staticmethod
    def _write_iracing_raw_channels(
        folder: Path,
        column_names: list[str],
        var_schema: list[dict[str, Any]] | None = None,
    ) -> None:
        """Write ``channels_iracing_raw.json``."""
        payload = build_raw_iracing_channels_payload(column_names, var_schema)
        (folder / "channels_iracing_raw.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    @staticmethod
    def cleanup_stale_temps(output_root: Path) -> int:
        """Remove leftover ``_tmp_*`` folders from previous crashes.

        Returns the number of cleaned-up folders.
        """
        count = 0
        if not output_root.exists():
            return count
        for p in output_root.iterdir():
            if p.is_dir() and p.name.startswith(_TEMP_PREFIX):
                log.warning("Removing stale temp session folder: %s", p)
                shutil.rmtree(p, ignore_errors=True)
                count += 1
        return count
