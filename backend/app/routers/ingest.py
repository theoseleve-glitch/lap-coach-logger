"""Ingest routes — the five POST endpoints the desktop talks to.

All routes share the same skeleton:
  1. Authenticated via device token (current_device).
  2. Idempotency-Key header parsed as UUID.
  3. Pydantic model validates payload.
  4. Check sync_envelopes for replay → HTTP 200 + already_seen=True.
  5. Insert business row(s) + envelope audit row in one transaction.
  6. IntegrityError on envelope_id UNIQUE → treat as replay.

The skeleton is small enough that repeating it per-route is clearer than
a helper with six callbacks.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas
from app.auth import DeviceIdentity, current_device
from app.database import get_db
from app.envelope import (
    derive_envelope_id,
    envelope_already_seen,
    idempotency_key,
    record_envelope,
)

router = APIRouter(tags=["ingest"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _accept(envelope_id: uuid.UUID, already_seen: bool = False) -> schemas.AcceptResponse:
    return schemas.AcceptResponse(envelope_id=envelope_id, already_seen=already_seen)


async def _require_session(db: AsyncSession, session_id: str, user_id: uuid.UUID) -> models.Session:
    """Ensure the parent session exists and belongs to this user."""
    session = (await db.execute(
        select(models.Session).where(
            models.Session.session_id == session_id,
            models.Session.user_id == user_id,
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "ok": False, "code": "missing_session",
                "message": "session not found; retry /sessions-start first",
            },
        )
    return session


# ---------------------------------------------------------------------------
# POST /sessions-start
# ---------------------------------------------------------------------------

@router.post("/sessions-start", response_model=schemas.AcceptResponse)
async def sessions_start(
    body: schemas.SessionIn,
    envelope_id: uuid.UUID = Depends(idempotency_key),
    ident: DeviceIdentity = Depends(current_device),
    db: AsyncSession = Depends(get_db),
) -> schemas.AcceptResponse:
    if await envelope_already_seen(db, envelope_id):
        return _accept(envelope_id, already_seen=True)

    # ON CONFLICT (envelope_id) DO NOTHING so retries where the envelope
    # audit row didn't land but the session did are still idempotent.
    stmt = pg_insert(models.Session).values(
        session_id=body.session_id,
        user_id=ident.user.id,
        device_token=ident.device.device_token,
        envelope_id=envelope_id,
        sim=body.sim,
        track=body.track,
        car=body.car,
        mode=body.mode,
        driver_name=body.driver_name,
        start_time=body.start_time,
        sample_count=body.sample_count,
    ).on_conflict_do_nothing(index_elements=["envelope_id"])

    try:
        await db.execute(stmt)
        await record_envelope(
            db, envelope_id=envelope_id, user_id=ident.user.id,
            device_token=ident.device.device_token,
            payload_type="session", session_id=body.session_id,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # UNIQUE violation on envelope_id — another request raced us.
        return _accept(envelope_id, already_seen=True)
    return _accept(envelope_id)


# ---------------------------------------------------------------------------
# POST /sessions-end
# ---------------------------------------------------------------------------

@router.post("/sessions-end", response_model=schemas.AcceptResponse)
async def sessions_end(
    body: schemas.SessionEndIn,
    envelope_id: uuid.UUID = Depends(idempotency_key),
    ident: DeviceIdentity = Depends(current_device),
    db: AsyncSession = Depends(get_db),
) -> schemas.AcceptResponse:
    if await envelope_already_seen(db, envelope_id):
        return _accept(envelope_id, already_seen=True)

    session = await _require_session(db, body.session_id, ident.user.id)
    session.end_time = body.end_time
    session.sample_count = body.sample_count
    session.updated_at = datetime.now(timezone.utc)

    await record_envelope(
        db, envelope_id=envelope_id, user_id=ident.user.id,
        device_token=ident.device.device_token,
        payload_type="session_end", session_id=body.session_id,
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return _accept(envelope_id, already_seen=True)
    return _accept(envelope_id)


# ---------------------------------------------------------------------------
# POST /laps-batch
# ---------------------------------------------------------------------------

@router.post("/laps-batch", response_model=schemas.AcceptResponse)
async def laps_batch(
    body: schemas.LapsBatchIn,
    envelope_id: uuid.UUID = Depends(idempotency_key),
    ident: DeviceIdentity = Depends(current_device),
    db: AsyncSession = Depends(get_db),
) -> schemas.AcceptResponse:
    session_id = body.laps[0].session_id
    await _require_session(db, session_id, ident.user.id)

    if await envelope_already_seen(db, envelope_id):
        return _accept(envelope_id, already_seen=True)

    rows = [
        {
            "session_id": lap.session_id,
            "user_id": ident.user.id,
            "envelope_id": derive_envelope_id(envelope_id, lap.lap_number),
            "lap_number": lap.lap_number,
            "lap_time_s": lap.lap_time_s,
            "valid": lap.valid,
            "fuel_used_l": lap.fuel_used_l,
            "sector_times_s": lap.sector_times_s,
            "consistency_pct": lap.consistency_pct,
            "std_dev_s": lap.std_dev_s,
        }
        for lap in body.laps
    ]
    stmt = pg_insert(models.Lap).values(rows).on_conflict_do_nothing(
        index_elements=["session_id", "lap_number"],
    )
    try:
        await db.execute(stmt)
        await record_envelope(
            db, envelope_id=envelope_id, user_id=ident.user.id,
            device_token=ident.device.device_token,
            payload_type="lap", session_id=session_id,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return _accept(envelope_id, already_seen=True)
    return _accept(envelope_id)


# ---------------------------------------------------------------------------
# POST /coaching-batch
# ---------------------------------------------------------------------------

@router.post("/coaching-batch", response_model=schemas.AcceptResponse)
async def coaching_batch(
    body: schemas.CoachingBatchIn,
    envelope_id: uuid.UUID = Depends(idempotency_key),
    ident: DeviceIdentity = Depends(current_device),
    db: AsyncSession = Depends(get_db),
) -> schemas.AcceptResponse:
    session_id = body.coaching[0].session_id
    await _require_session(db, session_id, ident.user.id)

    if await envelope_already_seen(db, envelope_id):
        return _accept(envelope_id, already_seen=True)

    rows = [
        {
            "session_id": c.session_id,
            "user_id": ident.user.id,
            "envelope_id": derive_envelope_id(envelope_id, i),
            "consistency_score": c.consistency_score,
            "trend": c.trend,
            "focus_area": c.focus_area,
            "recommendation": c.recommendation,
            "confidence": c.confidence,
            "emitted_at": c.timestamp,
        }
        for i, c in enumerate(body.coaching)
    ]
    stmt = pg_insert(models.CoachingOutput).values(rows).on_conflict_do_nothing(
        index_elements=["envelope_id"],
    )
    try:
        await db.execute(stmt)
        await record_envelope(
            db, envelope_id=envelope_id, user_id=ident.user.id,
            device_token=ident.device.device_token,
            payload_type="coaching", session_id=session_id,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return _accept(envelope_id, already_seen=True)
    return _accept(envelope_id)


# ---------------------------------------------------------------------------
# POST /events-batch
# ---------------------------------------------------------------------------

@router.post("/events-batch", response_model=schemas.AcceptResponse)
async def events_batch(
    body: schemas.EventsBatchIn,
    envelope_id: uuid.UUID = Depends(idempotency_key),
    ident: DeviceIdentity = Depends(current_device),
    db: AsyncSession = Depends(get_db),
) -> schemas.AcceptResponse:
    session_id = body.events[0].session_id
    await _require_session(db, session_id, ident.user.id)

    if await envelope_already_seen(db, envelope_id):
        return _accept(envelope_id, already_seen=True)

    rows = [
        {
            "session_id": ev.session_id,
            "user_id": ident.user.id,
            "envelope_id": derive_envelope_id(envelope_id, i),
            "event_type": ev.event_type,
            "occurred_at": ev.timestamp,
            "payload": ev.payload,
        }
        for i, ev in enumerate(body.events)
    ]
    stmt = pg_insert(models.SessionEvent).values(rows).on_conflict_do_nothing(
        index_elements=["envelope_id"],
    )
    try:
        await db.execute(stmt)
        await record_envelope(
            db, envelope_id=envelope_id, user_id=ident.user.id,
            device_token=ident.device.device_token,
            payload_type="event", session_id=session_id,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return _accept(envelope_id, already_seen=True)
    return _accept(envelope_id)
