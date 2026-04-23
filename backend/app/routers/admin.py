"""Admin routes — curator tooling for canonical registry triage.

These endpoints are not auth-gated in v1 (single-operator deployment).
For multi-tenant prod, add a role check before GA.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/drifts")
async def list_drifts(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List canonical drifts — where desktop and backend disagree."""
    result = await db.execute(
        select(models.CanonicalDrift)
        .order_by(models.CanonicalDrift.detected_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "session_id": r.session_id,
            "field": r.field,
            "submitted_value": r.submitted_value,
            "backend_value": r.backend_value,
            "sim_id": r.sim_id,
            "raw_value": r.raw_value,
            "desktop_lut_version": r.desktop_lut_version,
            "backend_lut_version": r.backend_lut_version,
            "detected_at": r.detected_at.isoformat() if r.detected_at else None,
        }
        for r in rows
    ]


@router.get("/unresolved")
async def list_unresolved(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List unresolved canonical mappings, sorted by most frequent first."""
    result = await db.execute(
        select(models.UnresolvedCanonical)
        .order_by(models.UnresolvedCanonical.occurrence_count.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "sim_id": r.sim_id,
            "raw_car": r.raw_car,
            "raw_track": r.raw_track,
            "raw_track_layout": r.raw_track_layout,
            "occurrence_count": r.occurrence_count,
            "first_seen_at": r.first_seen_at.isoformat() if r.first_seen_at else None,
            "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
        }
        for r in rows
    ]
