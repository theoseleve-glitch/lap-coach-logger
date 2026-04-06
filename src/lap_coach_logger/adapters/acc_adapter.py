"""Assetto Corsa Competizione telemetry adapter – real implementation.

ACC exposes telemetry through three Windows shared-memory files:
  - ``Local\\acpmf_physics``   – physics data (speed, g-force, inputs…)
  - ``Local\\acpmf_graphics``  – session state, lap info
  - ``Local\\acpmf_static``    – car / track names (written once per session)

This adapter opens all three via ``mmap``, reads the raw ctypes
structures defined in ``acc_shm_structs``, and maps them to the
normalised ``TelemetrySample`` schema.

If ACC is not running the mmap open will fail gracefully and the
adapter reports ``connected = False``.
"""

from __future__ import annotations

import ctypes
import logging
import mmap
import uuid
from datetime import datetime, timezone

from lap_coach_logger.adapters.acc_shm_structs import (
    SESSION_TYPE_MAP,
    SPageFileGraphic,
    SPageFilePhysics,
    SPageFileStatic,
)
from lap_coach_logger.adapters.base import SimAdapter
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.normalization.mapper import normalise_sample

log = logging.getLogger(__name__)

_ACC_EXES = ["acc.exe", "AC2-Win64-Shipping.exe"]

# ACC shared-memory tag names
_TAG_PHYSICS = "Local\\acpmf_physics"
_TAG_GRAPHICS = "Local\\acpmf_graphics"
_TAG_STATIC = "Local\\acpmf_static"

# ACC_STATUS values
_ACC_OFF = 0
_ACC_REPLAY = 1
_ACC_LIVE = 2
_ACC_PAUSE = 3


class ACCAdapter(SimAdapter):
    """Real adapter for ACC shared-memory telemetry."""

    def __init__(self) -> None:
        self._connected: bool = False
        self._session_uid: str = ""
        self._shm_physics: mmap.mmap | None = None
        self._shm_graphics: mmap.mmap | None = None
        self._shm_static: mmap.mmap | None = None
        # Cached static metadata
        self._track_name: str | None = None
        self._car_name: str | None = None
        self._track_length_m: float = 0.0
        self._fuel_capacity: float | None = None

    # -- SimAdapter interface -----------------------------------------------

    @property
    def sim_name(self) -> str:
        return "ACC"

    @property
    def process_names(self) -> list[str]:
        return list(_ACC_EXES)

    def connect(self) -> bool:
        """Open all three ACC shared-memory mappings."""
        try:
            self._shm_physics = mmap.mmap(
                -1, ctypes.sizeof(SPageFilePhysics), tagname=_TAG_PHYSICS, access=mmap.ACCESS_READ
            )
            self._shm_graphics = mmap.mmap(
                -1, ctypes.sizeof(SPageFileGraphic), tagname=_TAG_GRAPHICS, access=mmap.ACCESS_READ
            )
            self._shm_static = mmap.mmap(
                -1, ctypes.sizeof(SPageFileStatic), tagname=_TAG_STATIC, access=mmap.ACCESS_READ
            )
            self._connected = True
            self._session_uid = uuid.uuid4().hex[:12]
            self._read_static_metadata()
            log.info(
                "ACC adapter connected: track=%s car=%s uid=%s",
                self._track_name,
                self._car_name,
                self._session_uid,
            )
            return True
        except Exception:
            log.info("ACC shared memory not available – sim likely not running")
            self._close_mappings()
            return False

    def disconnect(self) -> None:
        log.info("ACC adapter: disconnecting")
        self._close_mappings()
        self._connected = False
        self._track_name = None
        self._car_name = None
        self._track_length_m = 0.0

    def is_session_active(self) -> bool:
        """Return True only when ACC status is LIVE (on-track driving)."""
        if not self._connected:
            return False
        try:
            gfx = self._read_graphics()
            return gfx.status == _ACC_LIVE
        except Exception:
            return False

    def read_sample(self) -> TelemetrySample | None:
        if not self._connected:
            return None

        try:
            phys = self._read_physics()
            gfx = self._read_graphics()

            raw = {
                "packetId": float(phys.packetId),
                "gas": float(phys.gas),
                "brake": float(phys.brake),
                "fuel": float(phys.fuel),
                "gear": int(phys.gear),
                "rpms": float(phys.rpms),
                "steerAngle": float(phys.steerAngle),
                "speedKmh": float(phys.speedKmh),
                "accG_x": float(phys.accG[0]),
                "accG_z": float(phys.accG[2]),
                "tc": float(phys.tc),
                "heading": float(phys.heading),
                "pitch": float(phys.pitch),
                "roll": float(phys.roll),
                "abs": float(phys.abs),
                "airTemp": float(phys.airTemp),
                "roadTemp": float(phys.roadTemp),
                "clutch": float(phys.clutch),
                "tyreCoreTemperature_0": float(phys.tyreCoreTemperature[0]),
                "tyreCoreTemperature_1": float(phys.tyreCoreTemperature[1]),
                "tyreCoreTemperature_2": float(phys.tyreCoreTemperature[2]),
                "tyreCoreTemperature_3": float(phys.tyreCoreTemperature[3]),
                "waterTemp": float(phys.waterTemp),
                "status": int(gfx.status),
                "session": int(gfx.session),
                "completedLaps": int(gfx.completedLaps),
                "iCurrentTime": int(gfx.iCurrentTime),
                "normalizedCarPosition": float(gfx.normalizedCarPosition),
                "isInPit": int(gfx.isInPit),
                "TC": int(gfx.TC),
                "ABS": int(gfx.ABS),
                "trackSPlineLength": float(self._track_length_m),
            }

            return normalise_sample(
                raw,
                sim=self.sim_name,
                passthrough={
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "session_uid": self._session_uid,
                    "fuel_capacity": self._fuel_capacity,
                    "track_name": self._track_name,
                    "car_name": self._car_name,
                },
            )
        except Exception:
            log.debug("Error reading ACC sample", exc_info=True)
            return None

    @property
    def connected(self) -> bool:
        return self._connected

    # -- internals ----------------------------------------------------------

    def _read_physics(self) -> SPageFilePhysics:
        buf = self._shm_physics
        assert buf is not None
        buf.seek(0)
        raw = buf.read(ctypes.sizeof(SPageFilePhysics))
        return SPageFilePhysics.from_buffer_copy(raw)

    def _read_graphics(self) -> SPageFileGraphic:
        buf = self._shm_graphics
        assert buf is not None
        buf.seek(0)
        raw = buf.read(ctypes.sizeof(SPageFileGraphic))
        return SPageFileGraphic.from_buffer_copy(raw)

    def _read_static(self) -> SPageFileStatic:
        buf = self._shm_static
        assert buf is not None
        buf.seek(0)
        raw = buf.read(ctypes.sizeof(SPageFileStatic))
        return SPageFileStatic.from_buffer_copy(raw)

    def _read_static_metadata(self) -> None:
        """Cache static info (track, car, spline length) – called once on connect."""
        try:
            static = self._read_static()
            self._track_name = static.track.strip("\x00").strip() or None
            self._car_name = static.carModel.strip("\x00").strip() or None
            self._track_length_m = float(static.trackSPlineLength) if static.trackSPlineLength > 0 else 0.0
            self._fuel_capacity = float(static.maxFuel) if static.maxFuel > 0 else None
        except Exception:
            log.debug("Could not read ACC static metadata", exc_info=True)

    def _close_mappings(self) -> None:
        for attr in ("_shm_physics", "_shm_graphics", "_shm_static"):
            shm = getattr(self, attr, None)
            if shm is not None:
                try:
                    shm.close()
                except Exception:
                    pass
                setattr(self, attr, None)
