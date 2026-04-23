"""Bundle upload + signed download routes.

POST /v1/bundles — multipart upload of the full session bundle.
GET  /v1/sessions/{session_id}/files/{filename} — signed download URL.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas
from app.auth import DeviceIdentity, current_device, current_user
from app.bundle_validator import ValidationError as BundleValidationError, ValidatedBundle, validate_bundle
from app.config import Settings, get_settings
from app.database import get_db
from app.envelope import derive_envelope_id, record_envelope
from app.resolver import BackendResolver, Drift
from app.storage import ObjectStore, bundle_file_key

log = logging.getLogger(__name__)

router = APIRouter(tags=["bundles"])

# Module-level singleton; wired by main.py lifespan.
_store: ObjectStore | None = None


def set_store(store: ObjectStore) -> None:
    global _store
    _store = store


def get_store() -> ObjectStore:
    if _store is None:
        raise HTTPException(500, detail={"ok": False, "code": "server_error", "message": "storage not configured"})
    return _store


# ---------------------------------------------------------------------------
# POST /v1/bundles
# ---------------------------------------------------------------------------

@router.post("/bundles", response_model=schemas.AcceptResponse)
async def upload_bundle(
    request: Request,
    ident: DeviceIdentity = Depends(current_device),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> schemas.AcceptResponse:
    """Accept a full session bundle as multipart/form-data."""

    # --- Content-Length pre-flight (D4) ---
    content_length = request.headers.get("content-length")
    if content_length is None:
        raise HTTPException(411, detail={"ok": False, "code": "length_required", "message": "Content-Length required"})
    if int(content_length) > settings.max_bundle_bytes:
        raise HTTPException(413, detail={
            "ok": False, "code": "bundle_too_large",
            "message": f"bundle exceeds {settings.max_bundle_bytes // (1024*1024)} MB cap",
        })

    # --- Read multipart parts ---
    form = await request.form()
    parts: dict[str, bytes] = {}
    total_bytes = 0
    for key in form:
        upload: UploadFile = form[key]  # type: ignore[assignment]
        data = await upload.read()
        total_bytes += len(data)
        if total_bytes > settings.max_bundle_bytes + 1024 * 1024:  # 1 MB slack
            raise HTTPException(413, detail={
                "ok": False, "code": "bundle_too_large",
                "message": f"bundle exceeds {settings.max_bundle_bytes // (1024*1024)} MB cap mid-stream",
            })
        parts[key] = data

    # --- Validate bundle ---
    result = validate_bundle(parts, idempotency_key, max_total_bytes=settings.max_bundle_bytes)
    if isinstance(result, BundleValidationError):
        raise HTTPException(
            status_code=400,
            detail={"ok": False, "code": result.code, "message": result.message, "field": result.field},
        )
    bundle: ValidatedBundle = result

    # --- Dedup check (step 15-16) ---
    existing = (await db.execute(
        select(models.SyncEnvelope).where(models.SyncEnvelope.envelope_id == bundle.bundle_hash_uuid)
    )).scalar_one_or_none()

    if existing:
        if existing.user_id == ident.user.id:
            return schemas.AcceptResponse(envelope_id=bundle.bundle_hash_uuid, already_seen=True)
        else:
            raise HTTPException(409, detail={
                "ok": False, "code": "bundle_owned_by_other_user",
                "message": "bundle_hash already accepted under a different user account",
            })

    # --- Resolver validation + drift detection (step 17) ---
    resolver = BackendResolver()
    drifts = await resolver.detect_drift(
        db,
        sim_id=bundle.sim_id,
        raw_car=bundle.raw_car,
        raw_track=bundle.raw_track,
        raw_layout=bundle.raw_track_layout,
        submitted_car_id=bundle.canonical_car_id,
        submitted_track_id=bundle.canonical_track_id,
        submitted_car_class=bundle.car_class,
        submitted_track_layout=bundle.track_layout,
    )

    # --- Record unresolved ---
    unresolved = bundle.manifest.get("canonical_resolution", {}).get("unresolved", [])
    if unresolved:
        for field_name in unresolved:
            raw_car = bundle.raw_car if field_name == "car" else None
            raw_track = bundle.raw_track if field_name in ("track", "layout") else None
            raw_layout = bundle.raw_track_layout if field_name == "layout" else None
            stmt = pg_insert(models.UnresolvedCanonical).values(
                sim_id=bundle.sim_id,
                raw_car=raw_car,
                raw_track=raw_track,
                raw_track_layout=raw_layout,
            ).on_conflict_do_update(
                constraint="unresolved_unique",
                set_={
                    "occurrence_count": models.UnresolvedCanonical.occurrence_count + 1,
                    "last_seen_at": datetime.now(timezone.utc),
                },
            )
            await db.execute(stmt)

    # --- Begin transaction (steps 18-27) ---
    # Upsert session
    session_stmt = pg_insert(models.Session).values(
        session_id=bundle.session_id,
        user_id=ident.user.id,
        device_token=ident.device.device_token,
        envelope_id=bundle.bundle_hash_uuid,
        sim=bundle.sim_id,
        track=bundle.raw_track,
        car=bundle.raw_car,
        mode=bundle.mode,
        driver_name=bundle.driver_name,
        start_time=bundle.start_time,
        end_time=bundle.end_time,
        sample_count=bundle.sample_count,
        canonical_car_id=bundle.canonical_car_id,
        canonical_track_id=bundle.canonical_track_id,
        car_class=bundle.car_class,
        track_layout=bundle.track_layout,
        analysis_json=bundle.analysis,
        bundle_hash=bundle.manifest.get("bundle_hash", ""),
        canonical_drift_flags=[d.field for d in drifts] if drifts else [],
        last_canonicalized_at=datetime.now(timezone.utc) if bundle.canonical_car_id or bundle.canonical_track_id else None,
    ).on_conflict_do_update(
        index_elements=["session_id"],
        set_={
            "end_time": bundle.end_time,
            "sample_count": bundle.sample_count,
            "canonical_car_id": bundle.canonical_car_id,
            "canonical_track_id": bundle.canonical_track_id,
            "car_class": bundle.car_class,
            "track_layout": bundle.track_layout,
            "analysis_json": bundle.analysis,
            "bundle_hash": bundle.manifest.get("bundle_hash", ""),
            "canonical_drift_flags": [d.field for d in drifts] if drifts else [],
            "updated_at": datetime.now(timezone.utc),
        },
    )
    await db.execute(session_stmt)

    # Bulk insert laps
    for i, lap in enumerate(bundle.laps):
        lap_stmt = pg_insert(models.Lap).values(
            session_id=bundle.session_id,
            user_id=ident.user.id,
            envelope_id=derive_envelope_id(bundle.bundle_hash_uuid, f"lap:{i}"),
            lap_number=lap.get("lap_number", i),
            lap_time_s=lap.get("lap_time_s", 0),
            valid=lap.get("valid", True),
            fuel_used_l=lap.get("fuel_used_l", 0),
            sector_times_s=lap.get("sector_times_s", []),
            consistency_pct=lap.get("consistency_pct"),
            std_dev_s=lap.get("std_dev_s"),
        ).on_conflict_do_nothing(constraint="laps_session_number_uq")
        await db.execute(lap_stmt)

    # Bulk insert events
    for i, ev in enumerate(bundle.events):
        ev_stmt = pg_insert(models.SessionEvent).values(
            session_id=bundle.session_id,
            user_id=ident.user.id,
            envelope_id=derive_envelope_id(bundle.bundle_hash_uuid, f"event:{i}"),
            event_type=str(ev.get("event_type", ""))[:64],
            occurred_at=ev.get("timestamp") or ev.get("occurred_at") or datetime.now(timezone.utc).isoformat(),
            payload=ev.get("payload", {}),
        ).on_conflict_do_nothing(index_elements=["envelope_id"])
        await db.execute(ev_stmt)

    # Record drifts
    lut_version = await resolver.get_lut_version(db)
    for d in drifts:
        db.add(models.CanonicalDrift(
            session_id=bundle.session_id,
            user_id=ident.user.id,
            field=d.field,
            submitted_value=d.submitted_value,
            backend_value=d.backend_value,
            sim_id=bundle.sim_id,
            raw_value=bundle.raw_car if "car" in d.field else bundle.raw_track,
            desktop_lut_version=bundle.lut_version,
            backend_lut_version=lut_version,
        ))

    # Sync envelope audit
    await record_envelope(
        db,
        envelope_id=bundle.bundle_hash_uuid,
        user_id=ident.user.id,
        device_token=ident.device.device_token,
        payload_type="bundle",
        session_id=bundle.session_id,
    )

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return schemas.AcceptResponse(envelope_id=bundle.bundle_hash_uuid, already_seen=True)

    # --- Store files in MinIO (outside transaction — DB is committed) ---
    store = get_store()
    user_id_str = str(ident.user.id)
    for filename, data in bundle.file_bytes.items():
        key = bundle_file_key(user_id_str, bundle.session_id, filename)
        ct = "application/json" if filename.endswith(".json") else "application/octet-stream"
        await asyncio.to_thread(store.put, key, data, ct)

    # Update telemetry_path on the session row
    session_row = await db.get(models.Session, bundle.session_id)
    if session_row:
        session_row.telemetry_path = bundle_file_key(user_id_str, bundle.session_id, "telemetry.parquet")
        raw_parquet = next((f for f in bundle.file_bytes if f.startswith("telemetry_") and f.endswith("_raw.parquet")), None)
        if raw_parquet:
            session_row.raw_telemetry_path = bundle_file_key(user_id_str, bundle.session_id, raw_parquet)
        await db.commit()

    log.info(
        "Bundle accepted: session=%s sim=%s car=%s track=%s drifts=%d",
        bundle.session_id, bundle.sim_id, bundle.raw_car, bundle.raw_track, len(drifts),
    )

    return schemas.AcceptResponse(envelope_id=bundle.bundle_hash_uuid, already_seen=False)


# ---------------------------------------------------------------------------
# GET /v1/sessions/{session_id}/files/{filename} — signed download
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/files/{filename}")
async def download_file(
    session_id: str,
    filename: str,
    db: AsyncSession = Depends(get_db),
    user: models.User = Depends(current_user),
) -> RedirectResponse:
    """Redirect to a MinIO pre-signed URL for the requested file."""
    session = (await db.execute(
        select(models.Session).where(
            models.Session.session_id == session_id,
            models.Session.user_id == user.id,
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(404, detail={"ok": False, "code": "session_not_found"})

    store = get_store()
    key = bundle_file_key(str(user.id), session_id, filename)
    exists = await asyncio.to_thread(store.exists, key)
    if not exists:
        raise HTTPException(404, detail={"ok": False, "code": "file_not_found", "field": filename})

    url = await asyncio.to_thread(store.presigned_url, key)
    return RedirectResponse(url=url, status_code=302)
