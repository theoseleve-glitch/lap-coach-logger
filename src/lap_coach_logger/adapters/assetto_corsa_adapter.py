"""Classic Assetto Corsa telemetry adapter via shared memory."""

from __future__ import annotations

import ctypes
import logging
import math
import mmap
import uuid
from datetime import datetime, timezone
from typing import Any

from lap_coach_logger.adapters.ac_shm_structs import (
    SESSION_TYPE_MAP,
    SPageFileGraphic,
    SPageFilePhysics,
    SPageFileStatic,
)
from lap_coach_logger.adapters.base import SimAdapter
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.normalization.mapper import normalise_sample

log = logging.getLogger(__name__)

_ASSETTO_CORSA_EXES = ["acs.exe", "AssettoCorsa.exe", "acs_x86.exe"]
_TAG_PHYSICS = "Local\\acpmf_physics"
_TAG_GRAPHICS = "Local\\acpmf_graphics"
_TAG_STATIC = "Local\\acpmf_static"

_AC_STATUS_OFF = 0
_AC_STATUS_REPLAY = 1
_AC_STATUS_LIVE = 2
_AC_STATUS_PAUSE = 3
_RAW_PREFIX = "ac__"


class AssettoCorsaAdapter(SimAdapter):
    """Adapter for the original Assetto Corsa shared-memory API."""

    def __init__(self) -> None:
        self._connected = False
        self._session_uid = ""
        self._shm_physics: mmap.mmap | None = None
        self._shm_graphics: mmap.mmap | None = None
        self._shm_static: mmap.mmap | None = None
        self._track_name: str | None = None
        self._track_configuration: str | None = None
        self._car_name: str | None = None
        self._fuel_capacity: float | None = None
        self._track_length_m: float = 0.0
        self._sector_count: int = 3

    @property
    def sim_name(self) -> str:
        return "Assetto Corsa"

    @property
    def process_names(self) -> list[str]:
        return list(_ASSETTO_CORSA_EXES)

    def connect(self) -> bool:
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
                "Assetto Corsa adapter connected: track=%s config=%s car=%s uid=%s",
                self._track_name,
                self._track_configuration,
                self._car_name,
                self._session_uid,
            )
            return True
        except Exception:
            log.info("Assetto Corsa shared memory not available")
            self._close_mappings()
            return False

    def disconnect(self) -> None:
        log.info("Assetto Corsa adapter: disconnecting")
        self._close_mappings()
        self._connected = False
        self._track_name = None
        self._track_configuration = None
        self._car_name = None
        self._fuel_capacity = None
        self._track_length_m = 0.0
        self._sector_count = 3

    def is_session_active(self) -> bool:
        if not self._connected:
            return False
        try:
            gfx = self._read_graphics()
            return gfx.status == _AC_STATUS_LIVE
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
                "isInPit": int(gfx.isInPit or gfx.isInPitLane),
                "trackSPlineLength": float(self._track_length_m),
            }

            return normalise_sample(
                raw,
                sim=self.sim_name,
                passthrough={
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "session_uid": self._session_uid,
                    "fuel_capacity": self._fuel_capacity,
                    "track_name": self._formatted_track_name(),
                    "car_name": self._car_name,
                    "session_type": SESSION_TYPE_MAP.get(int(gfx.session)),
                },
            )
        except Exception:
            log.debug("Error reading Assetto Corsa sample", exc_info=True)
            return None

    def read_dashboard_state(self) -> dict[str, Any] | None:
        if not self._connected:
            return None

        try:
            phys = self._read_physics()
            gfx = self._read_graphics()
            return {
                "lap_time_s": _milliseconds_to_seconds(gfx.iCurrentTime),
                "last_lap_time_s": _milliseconds_to_seconds(gfx.iLastTime),
                "best_lap_time_s": _milliseconds_to_seconds(gfx.iBestTime),
                "current_sector_index": _normalize_sector_index(gfx.currentSectorIndex),
                "last_sector_time_s": _milliseconds_to_seconds(gfx.lastSectorTime),
                "sector_count": self._sector_count,
                "fuel_level": _clean_float(phys.fuel),
                "session_status": _AC_STATUS_NAMES.get(int(gfx.status), f"status_{int(gfx.status)}"),
                "flag_state": _ac_flag_state(gfx.flag),
                "tyre_pressure_lf": _clean_float(phys.wheelsPressure[0]),
                "tyre_pressure_rf": _clean_float(phys.wheelsPressure[1]),
                "tyre_pressure_lr": _clean_float(phys.wheelsPressure[2]),
                "tyre_pressure_rr": _clean_float(phys.wheelsPressure[3]),
                "tyre_temp_lf": _clean_float(phys.tyreCoreTemperature[0]),
                "tyre_temp_rf": _clean_float(phys.tyreCoreTemperature[1]),
                "tyre_temp_lr": _clean_float(phys.tyreCoreTemperature[2]),
                "tyre_temp_rr": _clean_float(phys.tyreCoreTemperature[3]),
                "tyre_wear_lf": _clean_float(phys.tyreWear[0]),
                "tyre_wear_rf": _clean_float(phys.tyreWear[1]),
                "tyre_wear_lr": _clean_float(phys.tyreWear[2]),
                "tyre_wear_rr": _clean_float(phys.tyreWear[3]),
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
                "tc_level": _clean_float(phys.tc),
                "abs_level": _clean_float(phys.abs),
            }
        except Exception:
            log.debug("Error reading Assetto Corsa dashboard state", exc_info=True)
            return None

    @property
    def connected(self) -> bool:
        return self._connected

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
            log.debug("Error reading Assetto Corsa raw sample", exc_info=True)
            return None

    def read_session_info_snapshot(self) -> dict[str, Any] | None:
        if not self._connected:
            return None

        try:
            return {
                "static": self._struct_to_dict(self._read_static()),
                "graphics": self._struct_to_dict(self._read_graphics()),
            }
        except Exception:
            log.debug("Error reading Assetto Corsa session info snapshot", exc_info=True)
            return None

    def get_sdk_metadata(self) -> dict[str, Any]:
        return {
            "session_uid": self._session_uid,
            "track_name": self._formatted_track_name(),
            "car_name": self._car_name,
            "track_length_m": self._track_length_m,
        }

    def _read_physics(self) -> SPageFilePhysics:
        buf = self._shm_physics
        assert buf is not None
        buf.seek(0)
        return SPageFilePhysics.from_buffer_copy(buf.read(ctypes.sizeof(SPageFilePhysics)))

    def _read_graphics(self) -> SPageFileGraphic:
        buf = self._shm_graphics
        assert buf is not None
        buf.seek(0)
        return SPageFileGraphic.from_buffer_copy(buf.read(ctypes.sizeof(SPageFileGraphic)))

    def _read_static(self) -> SPageFileStatic:
        buf = self._shm_static
        assert buf is not None
        buf.seek(0)
        return SPageFileStatic.from_buffer_copy(buf.read(ctypes.sizeof(SPageFileStatic)))

    def _read_static_metadata(self) -> None:
        try:
            static = self._read_static()
            self._track_name = static.track.strip("\x00").strip() or None
            self._track_configuration = static.trackConfiguration.strip("\x00").strip() or None
            self._car_name = static.carModel.strip("\x00").strip() or None
            self._track_length_m = float(static.trackSPlineLength) if static.trackSPlineLength > 0 else 0.0
            self._fuel_capacity = float(static.maxFuel) if static.maxFuel > 0 else None
            self._sector_count = int(static.sectorCount) if int(static.sectorCount) > 0 else 3
        except Exception:
            log.debug("Could not read Assetto Corsa static metadata", exc_info=True)

    def _formatted_track_name(self) -> str | None:
        if self._track_name and self._track_configuration:
            return f"{self._track_name} ({self._track_configuration})"
        return self._track_name

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
            cls._flatten_value(f"{prefix}__{field_name}", getattr(struct_obj, field_name), out)

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


_AC_STATUS_NAMES = {
    _AC_STATUS_OFF: "off",
    _AC_STATUS_REPLAY: "replay",
    _AC_STATUS_LIVE: "live",
    _AC_STATUS_PAUSE: "paused",
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


def _normalize_sector_index(value: object) -> int | None:
    if not isinstance(value, int):
        return None
    return max(1, value + 1)


def _ac_flag_state(value: object) -> str | None:
    if not isinstance(value, int):
        return None
    if value <= 0:
        return None
    return f"flag_{value}"
