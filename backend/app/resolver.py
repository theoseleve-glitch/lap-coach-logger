"""Backend resolver — VALIDATION mode per D5.

The desktop pre-resolves canonical IDs at finalize time using its bundled
LUT. The backend re-resolves the same raw strings against its own
car_aliases / track_aliases tables and compares. Disagreements are
recorded as canonical drifts; the desktop's submitted values are NEVER
overwritten.

This module also supports backfill (scripts/backfill_resolver.py) where
it resolves sessions that predated the registry.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models


@dataclass(frozen=True)
class ResolvedCar:
    canonical_id: uuid.UUID
    canonical_name: str
    car_class: str | None


@dataclass(frozen=True)
class ResolvedTrack:
    canonical_id: uuid.UUID
    canonical_name: str
    canonical_layout: str | None


@dataclass(frozen=True)
class Drift:
    """One field where desktop and backend disagree."""
    field: str                    # "canonical_car_id" | "canonical_track_id" | "car_class" | "track_layout"
    submitted_value: str | None   # what the desktop sent
    backend_value: str | None     # what the backend resolved


class BackendResolver:
    """Stateless resolver. One instance per request is fine — no caching needed
    at this level because SQLAlchemy's connection pool + query plan cache handle
    the hot path.

    For the backfill script that resolves thousands of sessions, callers should
    reuse the same BackendResolver across the batch so the LRU cache in
    `_resolve_*` helpers warms up.
    """

    async def resolve_car(
        self, db: AsyncSession, sim_id: str, raw_car: str,
    ) -> ResolvedCar | None:
        result = await db.execute(
            select(models.CarAlias.canonical_id)
            .where(models.CarAlias.sim_id == sim_id)
            .where(models.CarAlias.raw_id == raw_car)
        )
        canonical_id = result.scalar_one_or_none()
        if canonical_id is None:
            return None
        car = await db.get(models.Car, canonical_id)
        if car is None:
            return None
        return ResolvedCar(
            canonical_id=car.canonical_id,
            canonical_name=car.canonical_name,
            car_class=car.car_class,
        )

    async def resolve_track(
        self,
        db: AsyncSession,
        sim_id: str,
        raw_track: str,
        raw_layout: str | None,
    ) -> ResolvedTrack | None:
        result = await db.execute(
            select(models.TrackAlias.canonical_id, models.TrackAlias.canonical_layout)
            .where(models.TrackAlias.sim_id == sim_id)
            .where(models.TrackAlias.raw_id == raw_track)
            .where(models.TrackAlias.raw_layout == (raw_layout or ""))
        )
        row = result.first()
        if row is None:
            return None
        canonical_id, canonical_layout = row
        track = await db.get(models.Track, canonical_id)
        if track is None:
            return None
        return ResolvedTrack(
            canonical_id=track.canonical_id,
            canonical_name=track.canonical_name,
            canonical_layout=canonical_layout,
        )

    async def detect_drift(
        self,
        db: AsyncSession,
        *,
        sim_id: str,
        raw_car: str,
        raw_track: str,
        raw_layout: str | None,
        submitted_car_id: uuid.UUID | None,
        submitted_track_id: uuid.UUID | None,
        submitted_car_class: str | None,
        submitted_track_layout: str | None,
    ) -> list[Drift]:
        """Compare desktop's submitted canonical IDs to backend-resolved values.

        Returns one Drift per disagreeing field (may be empty = no drift).
        Only compares when BOTH sides have a value — if either is None (unknown),
        no drift is reported (can't meaningfully disagree on the unknown).
        """
        drifts: list[Drift] = []

        backend_car = await self.resolve_car(db, sim_id, raw_car)
        if backend_car and submitted_car_id and backend_car.canonical_id != submitted_car_id:
            drifts.append(Drift(
                field="canonical_car_id",
                submitted_value=str(submitted_car_id),
                backend_value=str(backend_car.canonical_id),
            ))
        if backend_car and submitted_car_class is not None and backend_car.car_class != submitted_car_class:
            drifts.append(Drift(
                field="car_class",
                submitted_value=submitted_car_class,
                backend_value=backend_car.car_class,
            ))

        backend_track = await self.resolve_track(db, sim_id, raw_track, raw_layout)
        if backend_track and submitted_track_id and backend_track.canonical_id != submitted_track_id:
            drifts.append(Drift(
                field="canonical_track_id",
                submitted_value=str(submitted_track_id),
                backend_value=str(backend_track.canonical_id),
            ))
        if backend_track and submitted_track_layout is not None and backend_track.canonical_layout != submitted_track_layout:
            drifts.append(Drift(
                field="track_layout",
                submitted_value=submitted_track_layout,
                backend_value=backend_track.canonical_layout,
            ))

        return drifts

    async def get_lut_version(self, db: AsyncSession) -> str:
        """Return a hash-based version string for the current backend LUT.

        Derived from max(updated_at) across cars + tracks — monotonically
        increasing so the desktop can compare its local snapshot.
        """
        from sqlalchemy import func
        car_ts = await db.execute(select(func.max(models.Car.updated_at)))
        track_ts = await db.execute(select(func.max(models.Track.updated_at)))
        car_max = car_ts.scalar_one_or_none()
        track_max = track_ts.scalar_one_or_none()
        latest = max(t for t in (car_max, track_max) if t is not None) if (car_max or track_max) else None
        if latest is None:
            return "empty"
        return latest.strftime("%Y-%m-%dT%H:%M:%SZ")
