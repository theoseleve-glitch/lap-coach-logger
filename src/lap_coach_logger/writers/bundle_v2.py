"""Bundle v2 writer — produces session.json v2 + analysis.json at finalize.

Called by the finalizer after all v1 files are written. Adds the two
new files to the session directory and computes the bundle_hash over
the canonical file set.

Per D5: desktop resolves canonical IDs at finalize time using the
bundled LUT. The backend validates but does not overwrite.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lap_coach_logger import __version__
from lap_coach_logger.core.race_strategy import RaceStrategy
from lap_coach_logger.normalization.resolver import CanonicalResolver
from lap_coach_logger.writers.analysis_writer import build_analysis
from lap_coach_logger.writers.strategy_serializer import serialize_race_strategy
from lap_schemas.v1 import SessionManifest as SharedSessionManifest

log = logging.getLogger(__name__)

# The 6 canonical files that go into bundle_hash computation.
CANONICAL_FILES = (
    "session.json",
    "analysis.json",
    "telemetry.parquet",
    "laps.json",
    "events.json",
    "channels.json",
)

# Sim adapter names → canonical sim_id mapping.
SIM_ID_MAP: dict[str, str] = {
    "iRacing": "iracing",
    "ACC": "acc",
    "Assetto Corsa": "assetto_corsa",
    "Le Mans Ultimate": "lmu",
}


def write_bundle_v2(
    session_dir: Path,
    *,
    session_id: str,
    sim_name: str,
    raw_car: str,
    raw_track: str,
    raw_track_layout: str | None,
    session_type_raw: str,
    mode: str,
    driver_name: str,
    start_time: str,
    end_time: str,
    sample_count: int,
    duration_s: float,
    laps: list[dict[str, Any]],
    events: list[dict[str, Any]],
    quality_report: dict[str, Any] | None = None,
    resolver: CanonicalResolver | None = None,
    environment_tag: str = "",
    race_strategy: RaceStrategy | None = None,
) -> dict[str, Any]:
    """Write session.json v2 + analysis.json into ``session_dir``.

    Returns the completed manifest dict (session.json contents).
    Assumes v1 files (telemetry.parquet, laps.json, events.json,
    channels.json) are already present in ``session_dir``.

    T144: when ``race_strategy`` is provided, the serialised plan
    lands under a top-level ``race_strategy`` key in the manifest.
    Omitting it leaves the key absent so older sessions stay
    backwards-compatible (no noisy ``null`` field).
    """
    sim_id = SIM_ID_MAP.get(sim_name, sim_name.lower().replace(" ", "_"))
    resolver = resolver or CanonicalResolver()

    # --- Canonical resolution ---
    unresolved: list[str] = []
    car = resolver.resolve_car(sim_id, raw_car)
    track = resolver.resolve_track(sim_id, raw_track, raw_track_layout)

    if car is None:
        unresolved.append("car")
    if track is None:
        unresolved.append("track")

    # --- Build analysis.json ---
    analysis = build_analysis(
        laps=laps,
        events=events,
        sample_count=sample_count,
        duration_s=duration_s,
        quality_report=quality_report,
    )
    analysis_bytes = json.dumps(analysis, indent=2).encode("utf-8")
    (session_dir / "analysis.json").write_bytes(analysis_bytes)

    # --- Compute file hashes for the inventory ---
    file_entries: list[dict[str, Any]] = []
    for name in CANONICAL_FILES:
        path = session_dir / name
        if name == "session.json":
            # Self-referential — placeholder until after serialisation.
            file_entries.append({
                "name": name, "sha256": "self", "size_bytes": 0, "required": True,
            })
            continue
        if not path.exists():
            log.warning("Missing canonical file %s in %s", name, session_dir)
            continue
        data = path.read_bytes()
        file_entries.append({
            "name": name,
            "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
            "required": True,
        })

    # Optional files (raw sidecars)
    for p in session_dir.iterdir():
        if p.name in {e["name"] for e in file_entries}:
            continue
        if p.name in ("metadata.json", "quality_report.json"):
            continue  # v1 legacy, not in v2 inventory
        if p.is_file():
            data = p.read_bytes()
            file_entries.append({
                "name": p.name,
                "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
                "required": False,
            })

    # --- Compute bundle_hash ---
    bundle_hash_hex = _compute_bundle_hash(file_entries, session_dir)
    bundle_hash = f"sha256:{bundle_hash_hex}"

    # --- Native artifact ---
    native_artifact = None
    for p in session_dir.iterdir():
        if p.suffix in (".ibt", ".ldx") or p.name.endswith(".ibt.gz"):
            native_artifact = {
                "kind": p.suffix.lstrip(".").rstrip(".gz"),
                "filename": p.name,
                "size_bytes": p.stat().st_size,
                "sha256": "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest(),
                "in_bundle": True,
            }
            break

    # --- Build session.json v2 ---
    manifest: dict[str, Any] = {
        "schema_version": 2,
        "logger_version": __version__,
        "bundle_hash": bundle_hash,
        "session_id": session_id,
        "raw_source": {
            "sim_id": sim_id,
            "sim_display_name": sim_name,
            "game_build": None,
            "raw_car": raw_car,
            "raw_track": raw_track,
            "raw_track_layout": raw_track_layout,
            "session_type_raw": session_type_raw,
            "driver_name_raw": driver_name,
            "captured_at": start_time,
            "native_artifact": native_artifact,
        },
        "canonical_resolution": {
            "lut_version": resolver.lut_version,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "resolver_version": "1.0.0",
            "canonical_car_id": car.canonical_id if car else None,
            "canonical_car_name": car.canonical_name if car else None,
            "car_class": car.car_class if car else None,
            "canonical_track_id": track.canonical_id if track else None,
            "canonical_track_name": track.canonical_name if track else None,
            "canonical_track_layout": track.canonical_layout if track else None,
            "session_type_canonical": resolver.resolve_session_type(session_type_raw),
            "unresolved": unresolved,
        },
        "session": {
            "session_uid": session_id,
            "mode": mode,
            "environment_tag": environment_tag,
            "driver_name": driver_name,
            "start_time": start_time,
            "end_time": end_time,
            "duration_s": duration_s,
            "sample_count": sample_count,
            "lap_count": len(laps),
        },
        "analysis_readiness": {
            "ready_for_analysis": analysis["recommendation"]["verdict"] != "not_recommended",
            "blockers": analysis["recommendation"]["blockers"],
            "quality_score": analysis["session_quality"]["overall_score"],
            "completeness": analysis["session_quality"]["completeness"],
            "min_valid_laps_met": analysis["lap_summary"]["valid_laps"] >= 1,
        },
        "bundle_files": sorted(file_entries, key=lambda f: f["name"]),
    }

    # T144: post-attach the race_strategy section only when a plan
    # was provided. Keeps the manifest lean for non-strategy
    # sessions (no noisy `null` field).
    if race_strategy is not None:
        manifest["race_strategy"] = serialize_race_strategy(race_strategy)

    session_json_bytes = json.dumps(manifest, indent=2).encode("utf-8")

    # Update session.json's own size in the inventory
    for f in manifest["bundle_files"]:
        if f["name"] == "session.json":
            f["size_bytes"] = len(session_json_bytes)

    # Re-serialize with correct size
    session_json_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    # Phase 6: v2 is the canonical format. Write directly to session.json.
    (session_dir / "session.json").write_bytes(session_json_bytes)

    log.info(
        "Bundle v2 written: session=%s sim=%s car=%s→%s track=%s→%s unresolved=%s",
        session_id, sim_id,
        raw_car, car.canonical_name if car else "?",
        raw_track, track.canonical_name if track else "?",
        unresolved or "none",
    )

    return manifest


def write_bundle_v2_from_manifest(
    session_dir: Path,
    *,
    manifest: SharedSessionManifest,
    raw_car: str,
    raw_track: str,
    raw_track_layout: str | None,
    session_type_raw: str,
    mode: str,
    driver_name: str,
    laps: list[dict[str, Any]],
    events: list[dict[str, Any]],
    quality_report: dict[str, Any] | None = None,
    resolver: CanonicalResolver | None = None,
    environment_tag: str = "",
) -> dict[str, Any]:
    """Canonical entry point: derive bundle v2 kwargs from a ``SessionManifest`` (T040).

    Centralises the canonical→legacy translation that used to live
    inline in ``SessionFinalizer.finalize``. The legacy wire format
    (sim_display_name, duration_s, sample_count, start_time, end_time)
    is still what ``write_bundle_v2`` consumes — this helper is the
    single place that maps canonical field names onto it.
    """
    if not isinstance(manifest, SharedSessionManifest):
        raise TypeError(
            "write_bundle_v2_from_manifest(manifest=...) expects a "
            "lap_schemas.v1.SessionManifest instance; got "
            f"{type(manifest).__name__}"
        )
    return write_bundle_v2(
        session_dir,
        session_id=str(manifest.session_id),
        sim_name=manifest.sim_title or manifest.source,
        raw_car=raw_car,
        raw_track=raw_track,
        raw_track_layout=raw_track_layout,
        session_type_raw=session_type_raw,
        mode=mode,
        driver_name=driver_name,
        start_time=manifest.started_at.isoformat(),
        end_time=manifest.ended_at.isoformat(),
        sample_count=manifest.total_samples,
        duration_s=manifest.duration_seconds,
        laps=laps,
        events=events,
        quality_report=quality_report,
        resolver=resolver,
        environment_tag=environment_tag,
    )


def _compute_bundle_hash(file_entries: list[dict], session_dir: Path) -> str:
    """SHA-256 over canonical (required) files in name-sorted order."""
    canonical = sorted(
        (f for f in file_entries if f.get("required", False)),
        key=lambda f: f["name"],
    )
    h = hashlib.sha256()
    for entry in canonical:
        name = entry["name"]
        h.update(name.encode("utf-8"))
        h.update(b"\x00")
        if name == "session.json":
            h.update(b"self")
        else:
            hex_str = entry["sha256"].removeprefix("sha256:")
            try:
                h.update(bytes.fromhex(hex_str))
            except ValueError:
                h.update(hex_str.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()
