"""Read routes — webapp queries.

Every query filters by user_id so one user can never see another's
rows. There's no RLS here; the filtering is at the app layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas
from app.auth import current_user
from app.database import get_db


router = APIRouter(tags=["read"])


@router.get("/sessions", response_model=list[schemas.SessionSummary])
async def list_sessions(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: models.User = Depends(current_user),
) -> list[schemas.SessionSummary]:
    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "code": "invalid_limit", "message": "1..500"},
        )

    # Lap counts joined in one query (avoid N+1).
    lap_count_subq = (
        select(
            models.Lap.session_id.label("sid"),
            func.count(models.Lap.id).label("lap_count"),
        )
        .where(models.Lap.user_id == user.id)
        .group_by(models.Lap.session_id)
        .subquery()
    )

    # Join canonical car/track names. LEFT OUTER because canonical_*_id may be NULL.
    stmt = (
        select(
            models.Session,
            func.coalesce(lap_count_subq.c.lap_count, 0),
            models.Car.canonical_name.label("canonical_car_name"),
            models.Track.canonical_name.label("canonical_track_name"),
        )
        .outerjoin(lap_count_subq, lap_count_subq.c.sid == models.Session.session_id)
        .outerjoin(models.Car, models.Car.canonical_id == models.Session.canonical_car_id)
        .outerjoin(models.Track, models.Track.canonical_id == models.Session.canonical_track_id)
        .where(models.Session.user_id == user.id)
        .order_by(models.Session.start_time.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    return [
        schemas.SessionSummary(
            session_id=s.session_id,
            sim=s.sim, track=s.track, car=s.car, mode=s.mode,
            driver_name=s.driver_name,
            start_time=s.start_time, end_time=s.end_time,
            sample_count=s.sample_count, lap_count=int(lap_count),
            canonical_car_id=s.canonical_car_id,
            canonical_car_name=canonical_car_name,
            car_class=s.car_class,
            canonical_track_id=s.canonical_track_id,
            canonical_track_name=canonical_track_name,
            track_layout=s.track_layout,
        )
        for s, lap_count, canonical_car_name, canonical_track_name in rows
    ]


@router.get("/sessions/{session_id}", response_model=schemas.SessionDetail)
async def session_detail(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: models.User = Depends(current_user),
) -> schemas.SessionDetail:
    session = (await db.execute(
        select(models.Session).where(
            models.Session.session_id == session_id,
            models.Session.user_id == user.id,
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "code": "session_not_found"},
        )

    laps = (await db.execute(
        select(models.Lap)
        .where(models.Lap.session_id == session_id, models.Lap.user_id == user.id)
        .order_by(models.Lap.lap_number)
    )).scalars().all()

    coaching = (await db.execute(
        select(models.CoachingOutput)
        .where(models.CoachingOutput.session_id == session_id, models.CoachingOutput.user_id == user.id)
        .order_by(models.CoachingOutput.emitted_at)
    )).scalars().all()

    events = (await db.execute(
        select(models.SessionEvent)
        .where(models.SessionEvent.session_id == session_id, models.SessionEvent.user_id == user.id)
        .order_by(models.SessionEvent.occurred_at)
    )).scalars().all()

    envelope_count = (await db.execute(
        select(func.count(models.SyncEnvelope.envelope_id))
        .where(models.SyncEnvelope.session_id == session_id, models.SyncEnvelope.user_id == user.id)
    )).scalar_one()

    # Resolve canonical names from joined tables.
    canonical_car_name = None
    if session.canonical_car_id:
        car = await db.get(models.Car, session.canonical_car_id)
        if car:
            canonical_car_name = car.canonical_name

    canonical_track_name = None
    if session.canonical_track_id:
        track_row = await db.get(models.Track, session.canonical_track_id)
        if track_row:
            canonical_track_name = track_row.canonical_name

    return schemas.SessionDetail(
        session_id=session.session_id,
        sim=session.sim, track=session.track, car=session.car, mode=session.mode,
        driver_name=session.driver_name,
        start_time=session.start_time, end_time=session.end_time,
        sample_count=session.sample_count,
        source=session.source, schema_version=session.schema_version,
        device_token=session.device_token,
        envelope_count=envelope_count,
        canonical_car_id=session.canonical_car_id,
        canonical_car_name=canonical_car_name,
        car_class=session.car_class,
        canonical_track_id=session.canonical_track_id,
        canonical_track_name=canonical_track_name,
        track_layout=session.track_layout,
        bundle_hash=session.bundle_hash,
        analysis_json=session.analysis_json,
        laps=[schemas.LapOut.model_validate(l) for l in laps],
        coaching=[schemas.CoachingOut.model_validate(c) for c in coaching],
        events=[schemas.EventOut.model_validate(e) for e in events],
    )
