"""Bundle v2 validation — used by POST /v1/bundles.

Validates the multipart upload against the spec in
docs/specs/logger_output_v2_and_bundle_ingest_v1.md §9.3.

Returns a typed result so the router can branch on error code without
parsing strings. All validation happens synchronously on parsed data;
the router handles async I/O (MinIO, DB).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

SCHEMA_VERSION = 2
KNOWN_SIMS = {"iracing", "acc", "assetto_corsa", "lmu"}
KNOWN_MODES = {"sprint", "endurance", "coaching", "data"}

REQUIRED_FILES = frozenset({
    "session.json",
    "analysis.json",
    "telemetry.parquet",
    "laps.json",
    "events.json",
    "channels.json",
})


@dataclass(frozen=True)
class ValidationError:
    code: str
    message: str
    field: str | None = None


@dataclass
class ValidatedBundle:
    """Result of a successful validation pass."""
    manifest: dict[str, Any]      # parsed session.json
    analysis: dict[str, Any]      # parsed analysis.json
    laps: list[dict[str, Any]]    # parsed laps.json
    events: list[dict[str, Any]]  # parsed events.json
    channels: dict[str, Any]      # parsed channels.json
    file_bytes: dict[str, bytes]  # filename → raw bytes (all parts)
    bundle_hash_uuid: uuid.UUID   # first-32-hex-of-sha256, for Idempotency-Key
    # Extracted fields for convenience
    session_id: str = ""
    sim_id: str = ""
    raw_car: str = ""
    raw_track: str = ""
    raw_track_layout: str | None = None
    canonical_car_id: uuid.UUID | None = None
    canonical_track_id: uuid.UUID | None = None
    car_class: str | None = None
    track_layout: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    sample_count: int = 0
    driver_name: str = ""
    mode: str = "sprint"
    lut_version: str = ""


def validate_bundle(
    parts: dict[str, bytes],
    idempotency_key: str,
    max_total_bytes: int = 200 * 1024 * 1024,
) -> ValidatedBundle | ValidationError:
    """Run the full validation sequence on parsed multipart parts.

    ``parts`` maps filename → file bytes as received from the multipart
    body. ``idempotency_key`` is the raw Idempotency-Key header value.

    Returns either a ValidatedBundle (success) or a ValidationError
    (first failure — processing stops immediately).
    """

    # --- Step 6: session.json present ---
    if "session.json" not in parts:
        return ValidationError("missing_required_file", "required file missing", "session.json")

    # --- Step 7: parse session.json ---
    try:
        manifest = json.loads(parts["session.json"])
    except (json.JSONDecodeError, ValueError) as e:
        return ValidationError("invalid_schema", f"session.json parse error: {e}")

    if not isinstance(manifest, dict):
        return ValidationError("invalid_schema", "session.json must be a JSON object")

    # --- Step 8+9: schema_version ---
    sv = manifest.get("schema_version")
    if sv != SCHEMA_VERSION:
        return ValidationError(
            "unsupported_schema_version",
            f"only schema_version {SCHEMA_VERSION} supported, got {sv}",
        )

    # --- Step 10: sim_id ---
    raw_source = manifest.get("raw_source", {})
    sim_id = raw_source.get("sim_id", "")
    if sim_id not in KNOWN_SIMS:
        return ValidationError(
            "unknown_sim_id",
            f"sim_id {sim_id!r} is not supported",
            "raw_source.sim_id",
        )

    # --- Step 11: bundle_hash matches Idempotency-Key ---
    bundle_hash = manifest.get("bundle_hash", "")
    bundle_hash_hex = bundle_hash.removeprefix("sha256:") if isinstance(bundle_hash, str) else ""
    if len(bundle_hash_hex) < 32:
        return ValidationError("bundle_hash_mismatch", "bundle_hash missing or too short")
    # Convert first 32 hex chars to UUID for comparison with Idempotency-Key
    try:
        bundle_uuid = uuid.UUID(bundle_hash_hex[:32])
    except ValueError:
        return ValidationError("bundle_hash_mismatch", "bundle_hash is not valid hex")
    try:
        idem_uuid = uuid.UUID(idempotency_key)
    except ValueError:
        return ValidationError("missing_envelope_id", "Idempotency-Key must be a UUID matching bundle_hash")
    if bundle_uuid != idem_uuid:
        return ValidationError(
            "bundle_hash_mismatch",
            f"Idempotency-Key {idem_uuid} does not match bundle_hash {bundle_uuid}",
        )

    # --- Step 12: inventory match ---
    bundle_files = manifest.get("bundle_files", [])
    if not isinstance(bundle_files, list):
        return ValidationError("invalid_schema", "bundle_files must be an array", "bundle_files")

    declared_names = {f["name"] for f in bundle_files if isinstance(f, dict) and "name" in f}
    uploaded_names = set(parts.keys())

    # All required files must be declared AND uploaded
    for req in REQUIRED_FILES:
        if req not in declared_names:
            return ValidationError("missing_required_file", f"required file not in bundle_files", req)
        if req not in uploaded_names:
            return ValidationError("missing_required_file", f"required file not uploaded", req)

    # Every declared file must be uploaded
    missing = declared_names - uploaded_names
    if missing:
        return ValidationError("inventory_mismatch", f"declared but not uploaded: {missing}", list(missing)[0])

    # Every uploaded file must be declared (no extras)
    extra = uploaded_names - declared_names
    if extra:
        return ValidationError("inventory_mismatch", f"uploaded but not declared: {extra}", list(extra)[0])

    # --- Step 13: per-file hash verification ---
    for entry in bundle_files:
        name = entry.get("name", "")
        declared_hash = entry.get("sha256", "")
        if name == "session.json" and declared_hash == "self":
            continue  # self-referential hash handled separately
        if name not in parts:
            continue  # already caught above
        actual_hash = "sha256:" + hashlib.sha256(parts[name]).hexdigest()
        if declared_hash != actual_hash:
            return ValidationError(
                "file_hash_mismatch",
                f"file content does not match declared sha256",
                name,
            )

    # --- Step 14: recompute bundle_hash from canonical files ---
    computed = _compute_bundle_hash(parts, bundle_files)
    if computed != bundle_hash_hex:
        return ValidationError(
            "bundle_hash_mismatch",
            f"recomputed bundle_hash does not match submitted ({computed[:16]}... vs {bundle_hash_hex[:16]}...)",
        )

    # --- Total size check ---
    total = sum(len(b) for b in parts.values())
    if total > max_total_bytes:
        return ValidationError(
            "bundle_too_large",
            f"bundle exceeds {max_total_bytes // (1024*1024)} MB cap (got {total})",
        )

    # --- Parse remaining JSON files ---
    try:
        analysis = json.loads(parts["analysis.json"])
    except (json.JSONDecodeError, ValueError) as e:
        return ValidationError("invalid_schema", f"analysis.json parse error: {e}", "analysis.json")

    try:
        laps = json.loads(parts["laps.json"])
    except (json.JSONDecodeError, ValueError) as e:
        return ValidationError("invalid_schema", f"laps.json parse error: {e}", "laps.json")
    if not isinstance(laps, list):
        return ValidationError("invalid_schema", "laps.json must be an array", "laps.json")

    try:
        events = json.loads(parts["events.json"])
    except (json.JSONDecodeError, ValueError) as e:
        return ValidationError("invalid_schema", f"events.json parse error: {e}", "events.json")
    if not isinstance(events, list):
        return ValidationError("invalid_schema", "events.json must be an array", "events.json")

    try:
        channels = json.loads(parts["channels.json"])
    except (json.JSONDecodeError, ValueError) as e:
        return ValidationError("invalid_schema", f"channels.json parse error: {e}", "channels.json")

    # --- Validate session consistency ---
    session_block = manifest.get("session", {})
    session_id = manifest.get("session_id", "")
    session_uid = session_block.get("session_uid", "")
    if session_id and session_uid and session_id != session_uid:
        return ValidationError(
            "inconsistent_bundle",
            "session_id and session.session_uid do not match",
            "session.session_uid",
        )

    mode = session_block.get("mode", "sprint")
    if mode not in KNOWN_MODES:
        return ValidationError("invalid_schema", f"invalid mode: {mode}", "session.mode")

    # --- Extract canonical resolution ---
    canon = manifest.get("canonical_resolution", {})
    canonical_car_id = _parse_uuid_or_none(canon.get("canonical_car_id"))
    canonical_track_id = _parse_uuid_or_none(canon.get("canonical_track_id"))

    # --- Parse timestamps ---
    start_time = _parse_dt(session_block.get("start_time"))
    end_time = _parse_dt(session_block.get("end_time"))

    return ValidatedBundle(
        manifest=manifest,
        analysis=analysis,
        laps=laps,
        events=events,
        channels=channels,
        file_bytes=parts,
        bundle_hash_uuid=bundle_uuid,
        session_id=session_id,
        sim_id=sim_id,
        raw_car=raw_source.get("raw_car", ""),
        raw_track=raw_source.get("raw_track", ""),
        raw_track_layout=raw_source.get("raw_track_layout"),
        canonical_car_id=canonical_car_id,
        canonical_track_id=canonical_track_id,
        car_class=canon.get("car_class"),
        track_layout=canon.get("canonical_track_layout"),
        start_time=start_time,
        end_time=end_time,
        sample_count=session_block.get("sample_count", 0),
        driver_name=session_block.get("driver_name", ""),
        mode=mode,
        lut_version=canon.get("lut_version", ""),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_bundle_hash(parts: dict[str, bytes], bundle_files: list[dict]) -> str:
    """SHA-256 over canonical (required=true) files in name-sorted order.

    Per spec §9.5: for each file sorted by name ASCII, concatenate
    name (UTF-8) + \\x00 + sha256 (raw 32 bytes) + \\x00.
    session.json's own sha256 uses the literal "self".
    """
    canonical_entries = sorted(
        (f for f in bundle_files if f.get("required", False)),
        key=lambda f: f["name"],
    )
    h = hashlib.sha256()
    for entry in canonical_entries:
        name = entry["name"]
        h.update(name.encode("utf-8"))
        h.update(b"\x00")
        if name == "session.json":
            h.update(b"self")
        else:
            file_hash_hex = entry.get("sha256", "").removeprefix("sha256:")
            try:
                h.update(bytes.fromhex(file_hash_hex))
            except ValueError:
                h.update(file_hash_hex.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _parse_uuid_or_none(val: Any) -> uuid.UUID | None:
    if val is None:
        return None
    try:
        return uuid.UUID(str(val))
    except (TypeError, ValueError):
        return None


def _parse_dt(val: Any) -> datetime | None:
    if val is None or val == "":
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
