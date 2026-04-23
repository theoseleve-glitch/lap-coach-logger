"""Import canonical seed JSON into Postgres. Idempotent upsert.

Usage:
    DATABASE_URL=... python -m scripts.import_canonicals [--seed-dir backend/seed]

Reads canonical_cars.json and canonical_tracks.json from the seed
directory and upserts into cars, car_aliases, tracks, track_aliases.
Running twice with the same input is a no-op. Running after adding
entries inserts only the new rows.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

import asyncio
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import models
from app.database import configure_engine, get_db

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"


async def _import_cars(seed_dir: Path) -> int:
    """Upsert cars + car_aliases. Returns number of new cars inserted."""
    path = seed_dir / "canonical_cars.json"
    if not path.exists():
        print(f"SKIP: {path} not found")
        return 0

    entries = json.loads(path.read_text(encoding="utf-8"))
    count = 0

    async for db in get_db():
        for entry in entries:
            cid = uuid.UUID(entry["canonical_id"])

            # Upsert car
            stmt = pg_insert(models.Car).values(
                canonical_id=cid,
                canonical_name=entry["canonical_name"],
                car_class=entry.get("car_class"),
                manufacturer=entry.get("manufacturer"),
                model=entry.get("model"),
                year=entry.get("year"),
            ).on_conflict_do_update(
                index_elements=["canonical_id"],
                set_={
                    "canonical_name": entry["canonical_name"],
                    "car_class": entry.get("car_class"),
                    "manufacturer": entry.get("manufacturer"),
                    "model": entry.get("model"),
                    "year": entry.get("year"),
                },
            )
            result = await db.execute(stmt)
            if result.rowcount:
                count += 1

            # Upsert aliases
            for alias in entry.get("aliases", []):
                alias_stmt = pg_insert(models.CarAlias).values(
                    sim_id=alias["sim_id"],
                    raw_id=alias["raw_id"],
                    canonical_id=cid,
                ).on_conflict_do_update(
                    index_elements=["sim_id", "raw_id"],
                    set_={"canonical_id": cid},
                )
                await db.execute(alias_stmt)

        await db.commit()
    print(f"Cars: {count} upserted from {len(entries)} entries")
    return count


async def _import_tracks(seed_dir: Path) -> int:
    """Upsert tracks + track_aliases. Returns number of new tracks inserted."""
    path = seed_dir / "canonical_tracks.json"
    if not path.exists():
        print(f"SKIP: {path} not found")
        return 0

    entries = json.loads(path.read_text(encoding="utf-8"))
    count = 0

    async for db in get_db():
        for entry in entries:
            cid = uuid.UUID(entry["canonical_id"])

            stmt = pg_insert(models.Track).values(
                canonical_id=cid,
                canonical_name=entry["canonical_name"],
                country=entry.get("country"),
                length_m=entry.get("length_m"),
            ).on_conflict_do_update(
                index_elements=["canonical_id"],
                set_={
                    "canonical_name": entry["canonical_name"],
                    "country": entry.get("country"),
                    "length_m": entry.get("length_m"),
                },
            )
            result = await db.execute(stmt)
            if result.rowcount:
                count += 1

            for alias in entry.get("aliases", []):
                alias_stmt = pg_insert(models.TrackAlias).values(
                    sim_id=alias["sim_id"],
                    raw_id=alias["raw_id"],
                    raw_layout=alias.get("raw_layout", ""),
                    canonical_id=cid,
                    canonical_layout=alias.get("canonical_layout"),
                ).on_conflict_do_update(
                    index_elements=["sim_id", "raw_id", "raw_layout"],
                    set_={
                        "canonical_id": cid,
                        "canonical_layout": alias.get("canonical_layout"),
                    },
                )
                await db.execute(alias_stmt)

        await db.commit()
    print(f"Tracks: {count} upserted from {len(entries)} entries")
    return count


async def _run(seed_dir: Path) -> None:
    cars = await _import_cars(seed_dir)
    tracks = await _import_tracks(seed_dir)
    print(f"Import complete: {cars} cars, {tracks} tracks")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-dir", default=str(SEED_DIR), help="path to seed/ directory")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL env var is required", file=sys.stderr)
        return 2

    configure_engine(url)
    asyncio.run(_run(Path(args.seed_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
