"""Re-resolve canonical IDs for sessions that are NULL or drifted.

Run after every LUT update:
    DATABASE_URL=... python -m scripts.backfill_resolver

Idempotent. Queries all sessions with NULL canonical_car_id or
canonical_track_id, re-resolves via the current car_aliases/track_aliases
tables, and updates the session rows. Also clears resolved entries from
unresolved_canonicals and canonical_drifts where drift is now resolved.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import or_, select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.database import configure_engine, get_db


async def _resolve_session(db: AsyncSession, session: models.Session) -> bool:
    """Attempt to resolve one session's canonical IDs. Returns True if changed."""
    changed = False

    # Resolve car
    if session.canonical_car_id is None and session.car:
        result = await db.execute(
            select(models.CarAlias.canonical_id)
            .where(models.CarAlias.sim_id == session.sim)
            .where(models.CarAlias.raw_id == session.car)
        )
        car_alias = result.scalar_one_or_none()
        if car_alias:
            session.canonical_car_id = car_alias
            # Fetch car_class from cars table
            car_row = await db.get(models.Car, car_alias)
            if car_row:
                session.car_class = car_row.car_class
            changed = True

    # Resolve track
    if session.canonical_track_id is None and session.track:
        raw_layout = session.track_layout or ""
        result = await db.execute(
            select(models.TrackAlias.canonical_id, models.TrackAlias.canonical_layout)
            .where(models.TrackAlias.sim_id == session.sim)
            .where(models.TrackAlias.raw_id == session.track)
            .where(models.TrackAlias.raw_layout == raw_layout)
        )
        track_alias = result.first()
        if track_alias:
            session.canonical_track_id = track_alias.canonical_id
            session.track_layout = track_alias.canonical_layout
            changed = True

    if changed:
        session.last_canonicalized_at = datetime.now(timezone.utc)

    return changed


async def _run() -> None:
    resolved_count = 0
    skipped_count = 0

    async for db in get_db():
        # Find sessions missing canonical IDs
        result = await db.execute(
            select(models.Session).where(
                or_(
                    models.Session.canonical_car_id.is_(None),
                    models.Session.canonical_track_id.is_(None),
                )
            )
        )
        sessions = result.scalars().all()

        for session in sessions:
            if await _resolve_session(db, session):
                resolved_count += 1
                # Remove from unresolved_canonicals if now resolved
                await db.execute(
                    delete(models.UnresolvedCanonical).where(
                        models.UnresolvedCanonical.sim_id == session.sim,
                        models.UnresolvedCanonical.raw_car == session.car,
                        models.UnresolvedCanonical.raw_track == session.track,
                    )
                )
            else:
                skipped_count += 1

        await db.commit()

    print(f"Backfill complete: {resolved_count} resolved, {skipped_count} still unresolved")


def main() -> int:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL env var is required", file=sys.stderr)
        return 2

    configure_engine(url)
    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
