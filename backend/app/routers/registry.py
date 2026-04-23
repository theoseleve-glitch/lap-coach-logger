"""Registry endpoint — serves the current canonical LUT as JSON.

Desktop calls ``GET /v1/registry/snapshot?since=<lut_version>`` at
session finalize time (best-effort). Returns the full LUT if newer
than ``since``, or 304 Not Modified if unchanged.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.database import get_db
from app.resolver import BackendResolver

router = APIRouter(tags=["registry"])


@router.get("/registry/snapshot")
async def registry_snapshot(
    since: str = Query(default="", description="LUT version from the desktop's last fetch"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    resolver = BackendResolver()
    current_version = await resolver.get_lut_version(db)

    # If desktop already has this version, skip the payload.
    if since and since >= current_version:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)

    # Build the full snapshot: cars + tracks with aliases.
    cars_result = await db.execute(select(models.Car))
    cars = cars_result.scalars().all()

    car_aliases_result = await db.execute(select(models.CarAlias))
    car_aliases = car_aliases_result.scalars().all()

    tracks_result = await db.execute(select(models.Track))
    tracks = tracks_result.scalars().all()

    track_aliases_result = await db.execute(select(models.TrackAlias))
    track_aliases = track_aliases_result.scalars().all()

    # Group aliases by canonical_id for efficient JSON assembly.
    car_alias_map: dict[str, list[dict]] = {}
    for a in car_aliases:
        key = str(a.canonical_id)
        car_alias_map.setdefault(key, []).append({
            "sim_id": a.sim_id, "raw_id": a.raw_id,
        })

    track_alias_map: dict[str, list[dict]] = {}
    for a in track_aliases:
        key = str(a.canonical_id)
        track_alias_map.setdefault(key, []).append({
            "sim_id": a.sim_id, "raw_id": a.raw_id,
            "raw_layout": a.raw_layout, "canonical_layout": a.canonical_layout,
        })

    payload = {
        "lut_version": current_version,
        "cars": [
            {
                "canonical_id": str(c.canonical_id),
                "canonical_name": c.canonical_name,
                "car_class": c.car_class,
                "manufacturer": c.manufacturer,
                "model": c.model,
                "year": c.year,
                "aliases": car_alias_map.get(str(c.canonical_id), []),
            }
            for c in cars
        ],
        "tracks": [
            {
                "canonical_id": str(t.canonical_id),
                "canonical_name": t.canonical_name,
                "country": t.country,
                "length_m": t.length_m,
                "aliases": track_alias_map.get(str(t.canonical_id), []),
            }
            for t in tracks
        ],
    }

    return Response(
        content=json.dumps(payload),
        media_type="application/json",
        headers={"X-LUT-Version": current_version},
    )
