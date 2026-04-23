"""Desktop-side canonical resolver.

Resolves raw sim car/track strings to canonical IDs using the bundled
LUT at finalize time. Per D5: desktop is the first resolver; backend
validates but does not overwrite.

Usage at finalize time:

    resolver = CanonicalResolver()
    car = resolver.resolve_car("iracing", "Ferrari 296 GT3")
    track = resolver.resolve_track("iracing", "Monza", None)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from lap_coach_logger.normalization.lut_loader import (
    CarEntry,
    LUTData,
    TrackEntry,
    load_bundled_lut,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedCar:
    canonical_id: str
    canonical_name: str
    car_class: str | None


@dataclass(frozen=True)
class ResolvedTrack:
    canonical_id: str
    canonical_name: str
    canonical_layout: str | None


class CanonicalResolver:
    """Resolves raw sim strings → canonical IDs from the bundled LUT.

    One instance per finalize call. Optionally accepts a merged LUT
    (base + backend snapshot) for freshest resolution.
    """

    def __init__(self, lut: LUTData | None = None) -> None:
        self._lut = lut or load_bundled_lut()

    @property
    def lut_version(self) -> str:
        return self._lut.version

    def resolve_car(self, sim_id: str, raw_car: str) -> ResolvedCar | None:
        """Look up (sim_id, raw_car). Returns None on miss."""
        entry = self._lut.car_map.get((sim_id, raw_car))
        if entry is None:
            log.debug("Unresolved car: sim=%s raw=%s", sim_id, raw_car)
            return None
        return ResolvedCar(
            canonical_id=entry.canonical_id,
            canonical_name=entry.canonical_name,
            car_class=entry.car_class,
        )

    def resolve_track(
        self, sim_id: str, raw_track: str, raw_layout: str | None,
    ) -> ResolvedTrack | None:
        """Look up (sim_id, raw_track, raw_layout). Returns None on miss."""
        key = (sim_id, raw_track, raw_layout or "")
        entry = self._lut.track_map.get(key)
        if entry is None:
            log.debug("Unresolved track: sim=%s raw=%s layout=%s", sim_id, raw_track, raw_layout)
            return None
        return ResolvedTrack(
            canonical_id=entry.canonical_id,
            canonical_name=entry.canonical_name,
            canonical_layout=entry.canonical_layout,
        )

    def resolve_session_type(self, raw_type: str) -> str:
        """Canonical session type. Already handled by adapter enum maps —
        this is a pass-through for consistency in the resolution block."""
        return raw_type.lower().strip()
