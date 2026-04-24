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
import math
import mmap
import uuid
from datetime import datetime, timezone
from typing import Any

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
_RAW_PREFIX = "acc__"


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
        self._sector_count: int = 3

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
        self._sector_count = 3

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

    def read_dashboard_state(self) -> dict[str, Any] | None:
        if not self._connected:
            return None

        try:
            phys = self._read_physics()
            gfx = self._read_graphics()
            live_delta_s = _milliseconds_to_seconds(gfx.iDeltaLapTime)
            if live_delta_s is not None and not bool(gfx.isDeltaPositive):
                live_delta_s *= -1.0
            tyre_pressures = [
                _clean_float(phys.wheelsPressure[idx]) or _clean_float(getattr(gfx, f"mfdTyrePressure{suffix}"))
                for idx, suffix in enumerate(("LF", "RF", "LR", "RR"))
            ]
            return {
                "lap_time_s": _milliseconds_to_seconds(gfx.iCurrentTime),
                "last_lap_time_s": _milliseconds_to_seconds(gfx.iLastTime),
                "best_lap_time_s": _milliseconds_to_seconds(gfx.iBestTime),
                "live_delta_s": live_delta_s,
                "current_sector_index": _normalize_sector_index(gfx.currentSectorIndex),
                "last_sector_time_s": _milliseconds_to_seconds(gfx.lastSectorTime),
                "sector_count": self._sector_count,
                "fuel_level": _clean_float(phys.fuel),
                "fuel_per_lap_l": _clean_float(gfx.fuelXLap),
                "laps_remaining_est": _clean_float(gfx.fuelEstimatedLaps),
                "session_status": _ACC_STATUS_NAMES.get(int(gfx.status), f"status_{int(gfx.status)}"),
                "flag_state": _acc_flag_state(gfx),
                "tyre_pressure_lf": tyre_pressures[0],
                "tyre_pressure_rf": tyre_pressures[1],
                "tyre_pressure_lr": tyre_pressures[2],
                "tyre_pressure_rr": tyre_pressures[3],
                "tyre_temp_lf": _clean_float(phys.tyreCoreTemperature[0]),
                "tyre_temp_rf": _clean_float(phys.tyreCoreTemperature[1]),
                "tyre_temp_lr": _clean_float(phys.tyreCoreTemperature[2]),
                "tyre_temp_rr": _clean_float(phys.tyreCoreTemperature[3]),
                "tyre_wear_lf": _clean_float(phys.tyrewear[0]),
                "tyre_wear_rf": _clean_float(phys.tyrewear[1]),
                "tyre_wear_lr": _clean_float(phys.tyrewear[2]),
                "tyre_wear_rr": _clean_float(phys.tyrewear[3]),
                "brake_temp_lf": _clean_float(phys.brakeTemp[0]),
                "brake_temp_rf": _clean_float(phys.brakeTemp[1]),
                "brake_temp_lr": _clean_float(phys.brakeTemp[2]),
                "brake_temp_rr": _clean_float(phys.brakeTemp[3]),
                "ride_height_front": _clean_float(phys.rideHeight[0]),
                "ride_height_rear": _clean_float(phys.rideHeight[1]),
                "suspension_travel_lf": _clean_float(phys.suspensionTravel[0]),
                "suspension_travel_rf": _clean_float(phys.suspensionTravel[1]),
                "suspension_travel_lr": _clean_float(phys.suspensionTravel[2]),
                "suspension_travel_rr": _clean_float(phys.suspensionTravel[3]),
                "tc_level": int(gfx.TC) if int(gfx.TC) >= 0 else None,
                "abs_level": int(gfx.ABS) if int(gfx.ABS) >= 0 else None,
                "engine_map": int(gfx.EngineMap) if int(gfx.EngineMap) >= 0 else None,
                "brake_bias_pct": _normalize_percent(phys.brakeBias),
            }
        except Exception:
            log.debug("Error reading ACC dashboard state", exc_info=True)
            return None

    @property
    def connected(self) -> bool:
        return self._connected

    # -- extended capture interface -----------------------------------------

    def supports_raw_capture(self) -> bool:
        return True

    def read_raw_sample(self) -> dict[str, Any] | None:
        if not self._connected:
            return None

        try:
            row: dict[str, Any] = {}
            self._flatten_struct(self._read_physics(), f"{_RAW_PREFIX}physics", row)
            self._flatten_struct(self._read_graphics(), f"{_RAW_PREFIX}graphics", row)
            row[f"{_RAW_PREFIX}sample_timestamp_utc"] = datetime.now(timezone.utc).isoformat()
            return row
        except Exception:
            log.debug("Error reading ACC raw sample", exc_info=True)
            return None

    def read_session_info_snapshot(self) -> dict[str, Any] | None:
        if not self._connected:
            return None

        try:
            static = self._struct_to_dict(self._read_static())
            graphics = self._struct_to_dict(self._read_graphics())
            return {
                "static": static,
                "graphics": graphics,
            }
        except Exception:
            log.debug("Error reading ACC session info snapshot", exc_info=True)
            return None

    def get_sdk_metadata(self) -> dict[str, Any]:
        return {
            "session_uid": self._session_uid,
            "track_name": self._track_name,
            "car_name": self._car_name,
            "track_length_m": self._track_length_m,
        }

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
            self._sector_count = int(static.sectorCount) if int(static.sectorCount) > 0 else 3
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

    @classmethod
    def _flatten_struct(cls, struct_obj: ctypes.Structure, prefix: str, out: dict[str, Any]) -> None:
        for field_name, _ in getattr(struct_obj, "_fields_", []):
            value = getattr(struct_obj, field_name)
            cls._flatten_value(f"{prefix}__{field_name}", value, out)

    @classmethod
    def _flatten_value(cls, prefix: str, value: Any, out: dict[str, Any]) -> None:
        if isinstance(value, ctypes.Array):
            for idx, item in enumerate(value):
                cls._flatten_value(f"{prefix}__{idx}", item, out)
            return
        out[prefix] = cls._safe_raw_value(value)

    @classmethod
    def _struct_to_dict(cls, struct_obj: ctypes.Structure) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for field_name, _ in getattr(struct_obj, "_fields_", []):
            data[field_name] = cls._to_python(getattr(struct_obj, field_name))
        return data

    @classmethod
    def _to_python(cls, value: Any) -> Any:
        if isinstance(value, ctypes.Array):
            return [cls._to_python(item) for item in value]
        return cls._safe_raw_value(value)

    @staticmethod
    def _safe_raw_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, float):
            return None if math.isnan(value) or math.isinf(value) else value
        if isinstance(value, (int, bool, str)):
            return value
        return str(value)


_ACC_STATUS_NAMES = {
    _ACC_OFF: "off",
    _ACC_REPLAY: "replay",
    _ACC_LIVE: "live",
    _ACC_PAUSE: "paused",
}


def _clean_float(value: object) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _milliseconds_to_seconds(value: object) -> float | None:
    number = _clean_float(value)
    if number is None or number <= 0:
        return None
    return number / 1000.0


def _normalize_percent(value: object) -> float | None:
    number = _clean_float(value)
    if number is None:
        return None
    if 0.0 <= number <= 1.0:
        return round(number * 100.0, 2)
    return round(number, 2)


def _normalize_sector_index(value: object) -> int | None:
    if not isinstance(value, int):
        return None
    return max(1, value + 1)


def _acc_flag_state(gfx: SPageFileGraphic) -> str | None:
    if int(gfx.GlobalRed):
        return "red"
    if int(gfx.GlobalChequered):
        return "checkered"
    if int(gfx.GlobalYellow) or int(gfx.GlobalYellow1) or int(gfx.GlobalYellow2) or int(gfx.GlobalYellow3):
        return "yellow"
    if int(gfx.GlobalWhite):
        return "white"
    if int(gfx.GlobalGreen):
        return "green"
    track_status = str(gfx.trackStatus or "").strip("\x00").strip()
    if track_status:
        return track_status.lower()
    if int(gfx.flag) > 0:
        return f"flag_{int(gfx.flag)}"
    return None
