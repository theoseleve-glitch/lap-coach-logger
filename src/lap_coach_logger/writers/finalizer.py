"""Session finalization orchestrator.

Responsible for:
1. Creating a temp session folder.
2. Writing a structured **session bundle**:
   - ``session.json``  — manifest + metadata
   - ``telemetry.parquet`` (primary) or ``telemetry.csv`` (fallback)
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
from lap_coach_logger.coaching.rules_engine import (
    CoachingInsight,
    write_live_insights,
)
from lap_coach_logger.config.models import QualityConfig
from lap_coach_logger.core.schema import TELEMETRY_SCHEMA_VERSION, TelemetrySample
from lap_coach_logger.core.session_quality import validate_session_quality
from lap_coach_logger.core.sync_queue import SyncQueueManager
from lap_coach_logger.writers.bundle_schema import (
    BUNDLE_SCHEMA_VERSION,
    ChannelDef,
    LegacyLapRecord as LapRecord,
    SessionEvent,
    compute_file_sha256,
)
from lap_schemas.v1 import SessionManifest as SharedSessionManifest
from lap_coach_logger.writers.channels import (
    build_channels_payload,
    build_raw_channels_payload,
    build_raw_iracing_channels_payload,
)
from lap_coach_logger.writers.csv_writer import CsvWriter
from lap_coach_logger.writers.parquet_writer import ParquetWriter

log = logging.getLogger(__name__)

_TEMP_PREFIX = "_tmp_"
_RAW_CAPTURE_SLUGS = {
    "iRacing": "iracing",
    "ACC": "acc",
    "Assetto Corsa": "assetto_corsa",
    "Le Mans Ultimate": "lmu",
    "LMU": "lmu",
}


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


def _raw_capture_slug(sim_name: str | None) -> str | None:
    if not sim_name:
        return None
    return _RAW_CAPTURE_SLUGS.get(sim_name, _safe_slug(sim_name, fallback="raw").lower())


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
        manifest: SharedSessionManifest | None = None,
        started_at: datetime | None = None,
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
        raw_capture_sim: str | None = None,
        raw_samples: list[dict[str, Any]] | None = None,
        raw_columns: list[str] | None = None,
        raw_session_info: dict[str, Any] | None = None,
        raw_catalogs: dict[str, Any] | None = None,
        raw_var_schema: list[dict[str, Any]] | None = None,
        live_insights: list[CoachingInsight] | None = None,
        environment_tag: str | None = None,
    ) -> Path | None:
        """Write session bundle and return the final folder path (or None on total failure).

        T025 (step 1 of the rewrite): when ``manifest`` is a
        ``SessionManifest`` it becomes the authoritative source for
        session identity + timing + sim/track; the kwargs are used as
        fallback only when ``manifest`` is ``None`` (legacy path).
        """
        if manifest is not None:
            if not isinstance(manifest, SharedSessionManifest):
                raise TypeError(
                    "SessionFinalizer.finalize(manifest=...) expects a "
                    "lap_schemas.v1.SessionManifest instance; got "
                    f"{type(manifest).__name__}"
                )
            session_uid = str(manifest.session_id)
            started_at = manifest.started_at
            ended_at = manifest.ended_at
            sim = manifest.sim_title or sim
            track = manifest.track_layout or track
            adapter_name = adapter_name or manifest.capture_app

        if started_at is None:
            raise TypeError(
                "SessionFinalizer.finalize() requires either ``manifest`` or "
                "``started_at`` kwarg"
            )
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
        if raw_capture_sim is None and (
            iracing_raw_samples
            or iracing_session_info is not None
            or iracing_catalogs is not None
        ):
            raw_capture_sim = "iRacing"
        raw_samples = raw_samples if raw_samples is not None else iracing_raw_samples
        raw_columns = raw_columns if raw_columns is not None else iracing_raw_columns
        raw_session_info = raw_session_info if raw_session_info is not None else iracing_session_info
        raw_catalogs = raw_catalogs if raw_catalogs is not None else iracing_catalogs
        raw_var_schema = raw_var_schema if raw_var_schema is not None else iracing_var_schema

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
            raw_files: dict[str, str] = {}
            raw_slug = _raw_capture_slug(raw_capture_sim)
            if raw_slug and raw_samples:
                raw_file = self._write_raw_telemetry(
                    tmp_dir, raw_slug, raw_samples, raw_columns,
                )
                if raw_file:
                    raw_files[f"telemetry_{raw_slug}_raw"] = raw_file
                cols = raw_columns or sorted(raw_samples[0].keys())
                self._write_raw_channels(
                    tmp_dir,
                    raw_slug,
                    cols,
                    preview_row=raw_samples[0] if raw_samples else None,
                    var_schema=raw_var_schema,
                )
                raw_files[f"channels_{raw_slug}_raw"] = f"channels_{raw_slug}_raw.json"

            if raw_slug and raw_session_info is not None:
                session_info_name = f"session_info_{raw_slug}.json"
                (tmp_dir / session_info_name).write_text(
                    json.dumps(raw_session_info, indent=2, default=str),
                    encoding="utf-8",
                )
                raw_files[f"session_info_{raw_slug}"] = session_info_name

            if raw_slug and raw_catalogs is not None:
                catalogs_name = f"{raw_slug}_catalogs.json"
                (tmp_dir / catalogs_name).write_text(
                    json.dumps(raw_catalogs, indent=2, default=str),
                    encoding="utf-8",
                )
                raw_files[f"{raw_slug}_catalogs"] = catalogs_name

            # ── laps.json ──
            self._write_laps(tmp_dir, laps or [])

            # ── laps.parquet (Bundle v2, T028) ──
            # Only when a shared SessionManifest is supplied AND there is
            # at least one lap to persist. Rows keep the LegacyLapRecord
            # shape so the file round-trips via
            # ``LegacyLapRecord(**pyarrow_row)``.
            if manifest is not None and laps:
                self._write_laps_parquet(tmp_dir, laps)

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

            # ── coaching_insights.json (T099) ──
            # Live-generated insights from the rules engine —
            # tagged ``source: "client"`` so the server can
            # distinguish them from its own post-session
            # insights. ``None`` means "not configured" (file
            # absent); empty list means "ran clean" (file with
            # ``[]``); the server's audit path needs both
            # signals.
            if live_insights is not None:
                write_live_insights(tmp_dir, insights=live_insights)

            # ── session.json v2 + analysis.json (Phase 6: v2-only) ──
            # Extract car_name from extra before v2 writer consumes it.
            car_name = extra.pop("car", None)

            # Inject raw-capture file references into source_metadata
            # (generic path — works for iRacing, ACC, LMU, AC, etc.).
            if raw_files and raw_slug:
                extra["raw_capture"] = {
                    "sim": raw_capture_sim,
                    "files": raw_files,
                }
                extra[f"{raw_slug}_raw_files"] = raw_files
                if raw_samples:
                    extra["raw_capture"]["sample_count"] = len(raw_samples)
                    extra[f"{raw_slug}_raw_sample_count"] = len(raw_samples)

            from lap_coach_logger.writers.bundle_v2 import (
                write_bundle_v2,
                write_bundle_v2_from_manifest,
            )
            laps_payload = [l.to_dict() for l in (laps or [])]
            events_payload = [e.to_dict() for e in (events or [])]
            quality_payload = (
                quality_report.to_dict() if quality_report else None
            )
            # T040: route the manifest-supplied path through the canonical
            # adapter so session identity / timing / sample stats are
            # derived from the shared SessionManifest in one place.
            if manifest is not None:
                write_bundle_v2_from_manifest(
                    tmp_dir,
                    manifest=manifest,
                    raw_car=car_name or "",
                    raw_track=track or "",
                    raw_track_layout=extra.get("track_layout"),
                    session_type_raw=session_type or "",
                    mode=extra.get("mode", "sprint"),
                    driver_name=driver_name or "",
                    laps=laps_payload,
                    events=events_payload,
                    quality_report=quality_payload,
                    environment_tag=environment_tag or "",
                )
            else:
                write_bundle_v2(
                    tmp_dir,
                    session_id=session_uid or folder_name,
                    sim_name=sim or "",
                    raw_car=car_name or "",
                    raw_track=track or "",
                    raw_track_layout=extra.get("track_layout"),
                    session_type_raw=session_type or "",
                    mode=extra.get("mode", "sprint"),
                    driver_name=driver_name or "",
                    start_time=started_at.isoformat(),
                    end_time=ended_at.isoformat(),
                    sample_count=len(samples),
                    duration_s=duration_s,
                    laps=laps_payload,
                    events=events_payload,
                    quality_report=quality_payload,
                    environment_tag=environment_tag or "",
                )

            # ── manifest.json (Bundle v2 contract, T026/T030) ──
            # When a shared SessionManifest is supplied, emit the canonical
            # v2 manifest.json alongside the legacy session.json. Downstream
            # tooling reads manifest.json as the source of truth; the legacy
            # file stays for backward compat until T039 removes it.
            #
            # T030: populate ``telemetry_checksums`` with sha256 digests of
            # every bundle file we emitted so consumers can verify integrity.
            if manifest is not None:
                checksums = self._compute_bundle_checksums(tmp_dir)
                finalized_manifest = manifest.model_copy(
                    update={"telemetry_checksums": checksums}
                )
                (tmp_dir / "manifest.json").write_text(
                    finalized_manifest.model_dump_json(indent=2),
                    encoding="utf-8",
                )

            # ── atomic rename (shutil.move for Windows safety) ──
            if final_dir.exists():
                # Edge case: duplicate name — append disambiguator
                final_dir = self._output_root / f"{folder_name}_{ended_at.strftime('%f')}"
            shutil.move(str(tmp_dir), str(final_dir))
            log.info("Session bundle finalized → %s", final_dir)

            # T061: fire session_captured *after* the atomic rename so
            # only durable bundles count toward analytics funnels.
            # analytics.track is safe-noop when bootstrap hasn't wired
            # PostHog (dev runs, T065 opt-out, headless tests).
            # ``car_name`` was extracted upstream from extra.pop("car"),
            # so we use it directly instead of re-querying extra.
            from lap_coach_logger import analytics
            analytics.track(
                "session_captured",
                sim=sim,
                track=track,
                car=car_name,
                session_type=session_type,
                duration_s=duration_s,
            )

            return final_dir

        except Exception:
            log.exception("Session finalization failed")
            return None

    # ------------------------------------------------------------------
    def _write_telemetry(self, folder: Path, samples: list[TelemetrySample]) -> str:
        """Try Parquet first; fall back to CSV on any error."""
        fields = TelemetrySample.field_names()

        # Primary: Parquet (compact, typed, fast reads)
        parquet_path = folder / "telemetry.parquet"
        try:
            writer = ParquetWriter(compression=self._compression)
            writer.open(parquet_path, fields)
            writer.write_samples(samples)
            writer.close()
            return "parquet"
        except Exception:
            log.warning("Parquet write failed – falling back to CSV", exc_info=True)
            parquet_path.unlink(missing_ok=True)

        # Fallback: CSV
        csv_w: CsvWriter | None = None
        try:
            csv_w = CsvWriter()
            csv_w.open(folder / "telemetry.csv", fields)
            csv_w.write_samples(samples)
            csv_w.close()
            return "csv"
        except Exception:
            log.exception("CSV fallback also failed")
            if csv_w is not None:
                try:
                    csv_w.close()
                except Exception:
                    pass
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
    def _compute_bundle_checksums(folder: Path) -> dict[str, str]:
        """Return ``{filename: "sha256:HEX"}`` for every regular file in ``folder``.

        T030: consumers of the v2 bundle use these to verify integrity
        after transfer. ``manifest.json`` itself is excluded because it
        embeds the digests (would be a chicken-and-egg problem).
        """
        checksums: dict[str, str] = {}
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.name == "manifest.json":
                continue
            checksums[path.name] = (
                "sha256:" + compute_file_sha256(path)
            )
        return checksums

    # ------------------------------------------------------------------
    @staticmethod
    def _write_laps_parquet(folder: Path, laps: list[LapRecord]) -> None:
        """Write ``laps.parquet`` for Bundle v2 (T028).

        Each row mirrors the ``LegacyLapRecord`` dataclass, so consumers
        can reconstruct records via ``LegacyLapRecord(**row)``.
        """
        import pyarrow as pa
        import pyarrow.parquet as pq

        payload = [lap.to_dict() for lap in laps]
        table = pa.Table.from_pylist(payload)
        pq.write_table(table, folder / "laps.parquet")

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
    def _write_raw_telemetry_legacy_unused(
        self,
        folder: Path,
        raw_slug: str,
        raw_samples: list[dict[str, Any]],
        column_names: list[str] | None,
    ) -> str | None:
        """Write sim-specific raw telemetry CSV (primary) or Parquet (fallback).

        Returns the filename written, or None on total failure.
        """
        if not raw_samples:
            return None

        cols = column_names or sorted(raw_samples[0].keys())
        csv_name = f"telemetry_{raw_slug}_raw.csv"
        parquet_name = f"telemetry_{raw_slug}_raw.parquet"

        # Primary: CSV
        csv_path = folder / csv_name
        try:
            import csv as csv_mod
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv_mod.DictWriter(f, fieldnames=cols, extrasaction="ignore")
                writer.writeheader()
                for row in raw_samples:
                    writer.writerow({c: row.get(c) for c in cols})
            return csv_name
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
    def _write_iracing_raw_channels_legacy_unused(
        folder: Path,
        column_names: list[str],
        var_schema: list[dict[str, Any]] | None = None,
    ) -> None:
        """Write ``channels_iracing_raw.json``."""
        payload = build_raw_iracing_channels_payload(column_names, var_schema)
        (folder / "channels_iracing_raw.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _write_raw_csv(
        path: Path,
        raw_samples: list[dict[str, Any]],
        column_names: list[str],
    ) -> None:
        """Write a generic raw capture CSV file."""
        import csv as csv_mod
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv_mod.DictWriter(f, fieldnames=column_names, extrasaction="ignore")
            writer.writeheader()
            for row in raw_samples:
                writer.writerow({c: row.get(c) for c in column_names})

    # ------------------------------------------------------------------
    def _write_raw_telemetry(
        self,
        folder: Path,
        raw_slug: str,
        raw_samples: list[dict[str, Any]],
        column_names: list[str] | None,
    ) -> str | None:
        """Write sim-specific raw telemetry CSV (primary) or Parquet (fallback)."""
        if not raw_samples:
            return None

        cols = column_names or sorted(raw_samples[0].keys())
        csv_name = f"telemetry_{raw_slug}_raw.csv"
        parquet_name = f"telemetry_{raw_slug}_raw.parquet"

        try:
            import csv as csv_mod

            with open(folder / csv_name, "w", newline="", encoding="utf-8") as f:
                writer = csv_mod.DictWriter(f, fieldnames=cols, extrasaction="ignore")
                writer.writeheader()
                for row in raw_samples:
                    writer.writerow({c: row.get(c) for c in cols})
            return csv_name
        except Exception:
            log.warning("%s raw CSV write failed while falling back to Parquet", raw_slug, exc_info=True)
            (folder / csv_name).unlink(missing_ok=True)

        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            arrays = {col: [row.get(col) for row in raw_samples] for col in cols}
            table = pa.table(arrays)
            pq.write_table(table, folder / parquet_name, compression=self._compression)
            return parquet_name
        except Exception:
            log.exception("%s raw Parquet write also failed", raw_slug)
            return None

    # ------------------------------------------------------------------
    @staticmethod
    def _write_raw_channels(
        folder: Path,
        raw_slug: str,
        column_names: list[str],
        *,
        preview_row: dict[str, Any] | None = None,
        var_schema: list[dict[str, Any]] | None = None,
    ) -> None:
        """Write the sim-specific raw channel manifest."""
        if raw_slug == "iracing":
            payload = build_raw_iracing_channels_payload(column_names, var_schema)
        else:
            payload = build_raw_channels_payload(column_names, preview_row=preview_row)
        (folder / f"channels_{raw_slug}_raw.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    @staticmethod
    def cleanup_stale_temps(output_root: Path) -> int:
        """Remove leftover ``_tmp_*`` folders from previous crashes.

        Returns the number of cleaned-up folders.
        """
        count = 0
        if not output_root.exists() or not output_root.is_dir():
            return count
        for p in output_root.iterdir():
            if p.is_dir() and p.name.startswith(_TEMP_PREFIX):
                log.warning("Removing stale temp session folder: %s", p)
                shutil.rmtree(p, ignore_errors=True)
                count += 1
        return count
