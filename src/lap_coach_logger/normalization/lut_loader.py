"""Load canonical LUT files from the bundled package data.

The LUT files live at ``normalization/lut/canonical_cars.json`` and
``canonical_tracks.json``. They are snapshots from the backend's
``seed/`` directory, copied at build time by
``scripts/sync_lut_from_backend.py``.

The loader also supports an in-memory merge with a fresher snapshot
fetched from the backend at finalize time (best-effort, fails silently).
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

LUT_DIR = Path(__file__).parent / "lut"


@dataclass(frozen=True)
class CarEntry:
    canonical_id: str
    canonical_name: str
    car_class: str | None
    manufacturer: str | None
    model: str | None
    year: int | None


@dataclass(frozen=True)
class TrackEntry:
    canonical_id: str
    canonical_name: str
    country: str | None
    canonical_layout: str | None


@dataclass
class LUTData:
    """In-memory lookup tables. Keyed by (sim_id, raw_id)."""
    car_map: dict[tuple[str, str], CarEntry] = field(default_factory=dict)
    track_map: dict[tuple[str, str, str], TrackEntry] = field(default_factory=dict)
    version: str = "unknown"


def load_bundled_lut() -> LUTData:
    """Load from the package's bundled JSON files."""
    data = LUTData()

    cars_path = LUT_DIR / "canonical_cars.json"
    tracks_path = LUT_DIR / "canonical_tracks.json"

    if cars_path.exists():
        try:
            cars = json.loads(cars_path.read_text(encoding="utf-8"))
            for entry in cars:
                car = CarEntry(
                    canonical_id=entry["canonical_id"],
                    canonical_name=entry["canonical_name"],
                    car_class=entry.get("car_class"),
                    manufacturer=entry.get("manufacturer"),
                    model=entry.get("model"),
                    year=entry.get("year"),
                )
                for alias in entry.get("aliases", []):
                    key = (alias["sim_id"], alias["raw_id"])
                    data.car_map[key] = car
        except Exception:
            log.warning("Failed to load %s", cars_path, exc_info=True)

    if tracks_path.exists():
        try:
            tracks = json.loads(tracks_path.read_text(encoding="utf-8"))
            for entry in tracks:
                for alias in entry.get("aliases", []):
                    track = TrackEntry(
                        canonical_id=entry["canonical_id"],
                        canonical_name=entry["canonical_name"],
                        country=entry.get("country"),
                        canonical_layout=alias.get("canonical_layout"),
                    )
                    key = (alias["sim_id"], alias["raw_id"], alias.get("raw_layout", ""))
                    data.track_map[key] = track
        except Exception:
            log.warning("Failed to load %s", tracks_path, exc_info=True)

    # Version derived from file content hashes
    h = hashlib.sha256()
    for p in (cars_path, tracks_path):
        if p.exists():
            h.update(p.read_bytes())
    data.version = h.hexdigest()[:12]

    log.debug(
        "LUT loaded: %d cars, %d tracks, version=%s",
        len(data.car_map), len(data.track_map), data.version,
    )
    return data


def merge_backend_snapshot(base: LUTData, snapshot: dict[str, Any]) -> LUTData:
    """Merge a fresher snapshot from GET /v1/registry/snapshot into the base.

    New entries override existing ones by key. The version is updated to
    the snapshot's lut_version.
    """
    for car in snapshot.get("cars", []):
        entry = CarEntry(
            canonical_id=car["canonical_id"],
            canonical_name=car["canonical_name"],
            car_class=car.get("car_class"),
            manufacturer=car.get("manufacturer"),
            model=car.get("model"),
            year=car.get("year"),
        )
        for alias in car.get("aliases", []):
            base.car_map[(alias["sim_id"], alias["raw_id"])] = entry

    for track in snapshot.get("tracks", []):
        for alias in track.get("aliases", []):
            entry = TrackEntry(
                canonical_id=track["canonical_id"],
                canonical_name=track["canonical_name"],
                country=track.get("country"),
                canonical_layout=alias.get("canonical_layout"),
            )
            base.track_map[(alias["sim_id"], alias["raw_id"], alias.get("raw_layout", ""))] = entry

    base.version = snapshot.get("lut_version", base.version)
    return base
