"""Le Mans Ultimate live telemetry adapter via shared memory."""

from __future__ import annotations

import ctypes
import logging
import math
import mmap
import uuid
from datetime import datetime, timezone
from typing import Any

from lap_coach_logger.adapters.base import SimAdapter
from lap_coach_logger.adapters.lmu_shm_structs import (
    LMU_SHARED_MEMORY_TAG,
    MAX_VEHICLES,
    OPTIONS_LOCATION_ON_TRACK,
    SESSION_TYPE_MAP,
    SharedMemoryLayout,
    TelemInfoV01,
    VehicleScoringInfoV01,
)
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.normalization.mapper import normalise_sample

log = logging.getLogger(__name__)

_LMU_EXES = ["Le Mans Ultimate.exe", "LeMansUltimate.exe"]
_RAW_PREFIX = "lmu__"
_PIT_STATES = {1, 2, 3, 4}
_G_MPS2 = 9.80665


class LMUAdapter(SimAdapter):
    """Adapter for Le Mans Ultimate's official LMU_Data shared memory."""

    def __init__(self) -> None:
        self._connected = False
        self._session_uid = ""
        self._shm: mmap.mmap | None = None
        self._track_name: str | None = None
        self._car_name: str | None = None
        self._session_type: str | None = None
        self._fuel_capacity: float | None = None
        self._driver_name: str | None = None
        self._track_length_m: float = 0.0
        self._game_version: int | None = None

    @property
    def sim_name(self) -> str:
        return "Le Mans Ultimate"

    @property
    def process_names(self) -> list[str]:
        return list(_LMU_EXES)

    def connect(self) -> bool:
        try:
            self._shm = mmap.mmap(
                -1,
                ctypes.sizeof(SharedMemoryLayout),
                tagname=LMU_SHARED_MEMORY_TAG,
                access=mmap.ACCESS_READ,
            )
            self._connected = True
            self._session_uid = uuid.uuid4().hex[:12]
            layout = self._read_layout()
            self._refresh_context(layout)
            log.info(
                "LMU adapter connected: track=%s car=%s session=%s uid=%s version=%s",
                self._track_name,
                self._car_name,
                self._session_type,
                self._session_uid,
                self._game_version,
            )
            return True
        except Exception:
            log.info("LMU shared memory not available")
            self._close_mapping()
            return False

    def disconnect(self) -> None:
        log.info("LMU adapter: disconnecting")
        self._close_mapping()
        self._connected = False
        self._track_name = None
        self._car_name = None
        self._session_type = None
        self._fuel_capacity = None
        self._driver_name = None
        self._track_length_m = 0.0
        self._game_version = None

    def is_session_active(self) -> bool:
        if not self._connected:
            return False
        try:
            layout = self._read_layout()
            data = layout.data
            in_realtime = bool(data.scoring.scoringInfo.mInRealtime)
            on_track_ui = int(data.generic.appInfo.mOptionsLocation) == OPTIONS_LOCATION_ON_TRACK
            return bool(data.telemetry.playerHasVehicle) and (in_realtime or on_track_ui)
        except Exception:
            return False

    def read_sample(self) -> TelemetrySample | None:
        if not self._connected:
            return None

        try:
            layout = self._read_layout()
            player_telem = self._get_player_telemetry(layout)
            if player_telem is None:
                return None

            player_scoring = self._get_player_scoring(layout, telem_id=int(player_telem.mID))
            self._refresh_context(layout, player_telem=player_telem, player_scoring=player_scoring)

            speed_mps = math.sqrt(
                float(player_telem.mLocalVel.x) ** 2
                + float(player_telem.mLocalVel.y) ** 2
                + float(player_telem.mLocalVel.z) ** 2
            )
            lap_distance = float(player_scoring.mLapDist) if player_scoring is not None else None
            lap_dist_pct = None
            if lap_distance is not None and self._track_length_m > 0:
                lap_dist_pct = max(0.0, min(1.0, lap_distance / self._track_length_m))
            steering_range = float(player_telem.mPhysicalSteeringWheelRange or player_telem.mVisualSteeringWheelRange)
            steering_deg = float(player_telem.mFilteredSteering) * (steering_range / 2.0) if steering_range else None
            in_pits = self._is_in_pits(player_scoring)

            raw = {
                "Session Time": float(layout.data.scoring.scoringInfo.mCurrentET),
                "GPS Time": float(player_telem.mElapsedTime),
                "Lap": int(player_telem.mLapNumber),
                "Lap Dist": lap_distance,
                "Lap Dist Pct": lap_dist_pct,
                "Ground Speed": speed_mps,
                "Throttle Pos": float(player_telem.mFilteredThrottle),
                "Brake Pos": float(player_telem.mFilteredBrake),
                "Clutch Pos": float(player_telem.mFilteredClutch),
                "Steered Angle": steering_deg,
                "Gear": int(player_telem.mGear),
                "Engine RPM": float(player_telem.mEngineRPM),
                "World Pos X": float(player_telem.mPos.x),
                "World Pos Y": float(player_telem.mPos.y),
                "World Pos Z": float(player_telem.mPos.z),
                "Lateral Acceleration": self._meters_to_g(float(player_telem.mLocalAccel.x)),
                "Longitudinal Acceleration": self._meters_to_g(-float(player_telem.mLocalAccel.z)),
                "Track Temperature": float(layout.data.scoring.scoringInfo.mTrackTemp),
                "Ambient Temperature": float(layout.data.scoring.scoringInfo.mAmbientTemp),
                "Fuel Level": float(player_telem.mFuel),
                "Engine Water Temp": float(player_telem.mEngineWaterTemp),
                "Engine Oil Temp": float(player_telem.mEngineOilTemp),
                "Tyre Temp LF": self._kelvin_to_c(player_telem.mWheel[0].mTemperature[1]),
                "Tyre Temp RF": self._kelvin_to_c(player_telem.mWheel[1].mTemperature[1]),
                "Tyre Temp LR": self._kelvin_to_c(player_telem.mWheel[2].mTemperature[1]),
                "Tyre Temp RR": self._kelvin_to_c(player_telem.mWheel[3].mTemperature[1]),
                "In Pits": in_pits,
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
                    "session_type": self._session_type,
                    "is_on_track": self.is_session_active(),
                    "is_in_pits": in_pits,
                },
            )
        except Exception:
            log.debug("Error reading LMU sample", exc_info=True)
            return None

    def read_dashboard_state(self) -> dict[str, Any] | None:
        if not self._connected:
            return None

        try:
            layout = self._read_layout()
            player_telem = self._get_player_telemetry(layout)
            if player_telem is None:
                return None

            player_scoring = self._get_player_scoring(layout, telem_id=int(player_telem.mID))
            scoring_info = layout.data.scoring.scoringInfo
            last_sector_1 = _clean_float(getattr(player_scoring, "mLastSector1", None)) if player_scoring else None
            last_sector_2 = _clean_float(getattr(player_scoring, "mLastSector2", None)) if player_scoring else None
            last_lap_time = _clean_float(getattr(player_scoring, "mLastLapTime", None)) if player_scoring else None
            sector_3 = None
            if (
                last_lap_time is not None
                and last_sector_1 is not None
                and last_sector_2 is not None
                and last_lap_time > last_sector_1 + last_sector_2
            ):
                sector_3 = last_lap_time - last_sector_1 - last_sector_2

            return {
                "lap_time_s": _clean_float(getattr(player_scoring, "mTimeIntoLap", None)),
                "last_lap_time_s": last_lap_time,
                "best_lap_time_s": _clean_float(getattr(player_scoring, "mBestLapTime", None)) if player_scoring else None,
                "live_delta_s": _clean_float(player_telem.mDeltaBest),
                "current_sector_index": _lmu_sector_index(int(player_telem.mCurrentSector)),
                "sector_count": 3,
                "sector_1_time_s": (
                    _clean_float(getattr(player_scoring, "mCurSector1", None)) if player_scoring else None
                ) or last_sector_1,
                "sector_2_time_s": (
                    _clean_float(getattr(player_scoring, "mCurSector2", None)) if player_scoring else None
                ) or last_sector_2,
                "sector_3_time_s": sector_3,
                "fuel_level": _clean_float(player_telem.mFuel),
                "session_status": _lmu_session_status(scoring_info.mGamePhase),
                "flag_state": _lmu_flag_state(scoring_info.mYellowFlagState, player_scoring),
                "tyre_pressure_lf": _clean_float(player_telem.mWheel[0].mPressure),
                "tyre_pressure_rf": _clean_float(player_telem.mWheel[1].mPressure),
                "tyre_pressure_lr": _clean_float(player_telem.mWheel[2].mPressure),
                "tyre_pressure_rr": _clean_float(player_telem.mWheel[3].mPressure),
                "tyre_temp_lf": self._kelvin_to_c(player_telem.mWheel[0].mTemperature[1]),
                "tyre_temp_rf": self._kelvin_to_c(player_telem.mWheel[1].mTemperature[1]),
                "tyre_temp_lr": self._kelvin_to_c(player_telem.mWheel[2].mTemperature[1]),
                "tyre_temp_rr": self._kelvin_to_c(player_telem.mWheel[3].mTemperature[1]),
                "tyre_wear_lf": _clean_float(player_telem.mWheel[0].mWear),
                "tyre_wear_rf": _clean_float(player_telem.mWheel[1].mWear),
                "tyre_wear_lr": _clean_float(player_telem.mWheel[2].mWear),
                "tyre_wear_rr": _clean_float(player_telem.mWheel[3].mWear),
                "brake_temp_lf": _clean_float(player_telem.mWheel[0].mBrakeTemp),
                "brake_temp_rf": _clean_float(player_telem.mWheel[1].mBrakeTemp),
                "brake_temp_lr": _clean_float(player_telem.mWheel[2].mBrakeTemp),
                "brake_temp_rr": _clean_float(player_telem.mWheel[3].mBrakeTemp),
                "brake_bias_pct": _normalize_percent(player_telem.mRearBrakeBias),
            }
        except Exception:
            log.debug("Error reading LMU dashboard state", exc_info=True)
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
            layout = self._read_layout()
            player_telem = self._get_player_telemetry(layout)
            if player_telem is None:
                return None

            player_scoring = self._get_player_scoring(layout, telem_id=int(player_telem.mID))
            row: dict[str, Any] = {
                f"{_RAW_PREFIX}active_vehicles": int(layout.data.telemetry.activeVehicles),
                f"{_RAW_PREFIX}player_vehicle_idx": int(layout.data.telemetry.playerVehicleIdx),
                f"{_RAW_PREFIX}player_has_vehicle": bool(layout.data.telemetry.playerHasVehicle),
                f"{_RAW_PREFIX}sample_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            self._flatten_struct(layout.data.generic, f"{_RAW_PREFIX}generic", row)
            self._flatten_struct(layout.data.scoring.scoringInfo, f"{_RAW_PREFIX}scoring_info", row)
            if player_scoring is not None:
                self._flatten_struct(player_scoring, f"{_RAW_PREFIX}player_scoring", row)
            self._flatten_struct(player_telem, f"{_RAW_PREFIX}player_telemetry", row)
            return row
        except Exception:
            log.debug("Error reading LMU raw sample", exc_info=True)
            return None

    def read_session_info_snapshot(self) -> dict[str, Any] | None:
        if not self._connected:
            return None

        try:
            layout = self._read_layout()
            player_telem = self._get_player_telemetry(layout)
            player_scoring = None
            if player_telem is not None:
                player_scoring = self._get_player_scoring(layout, telem_id=int(player_telem.mID))
            return {
                "generic": self._struct_to_dict(layout.data.generic),
                "paths": self._struct_to_dict(layout.data.paths),
                "scoring_info": self._struct_to_dict(layout.data.scoring.scoringInfo),
                "active_vehicles": int(layout.data.telemetry.activeVehicles),
                "player_vehicle_idx": int(layout.data.telemetry.playerVehicleIdx),
                "player_has_vehicle": bool(layout.data.telemetry.playerHasVehicle),
                "player_scoring": self._struct_to_dict(player_scoring) if player_scoring is not None else None,
                "player_telemetry": self._struct_to_dict(player_telem) if player_telem is not None else None,
            }
        except Exception:
            log.debug("Error reading LMU session info snapshot", exc_info=True)
            return None

    def get_sdk_metadata(self) -> dict[str, Any]:
        return {
            "session_uid": self._session_uid,
            "track_name": self._track_name,
            "car_name": self._car_name,
            "driver_name": self._driver_name,
            "session_type": self._session_type,
            "track_length_m": self._track_length_m,
            "game_version": self._game_version,
        }

    def _read_layout(self) -> SharedMemoryLayout:
        buf = self._shm
        assert buf is not None
        buf.seek(0)
        raw = buf.read(ctypes.sizeof(SharedMemoryLayout))
        return SharedMemoryLayout.from_buffer_copy(raw)

    def _refresh_context(
        self,
        layout: SharedMemoryLayout,
        *,
        player_telem: TelemInfoV01 | None = None,
        player_scoring: VehicleScoringInfoV01 | None = None,
    ) -> None:
        if player_telem is None:
            player_telem = self._get_player_telemetry(layout)
        if player_scoring is None and player_telem is not None:
            player_scoring = self._get_player_scoring(layout, telem_id=int(player_telem.mID))

        scoring_info = layout.data.scoring.scoringInfo
        self._track_name = self._decode_text(scoring_info.mTrackName)
        self._session_type = SESSION_TYPE_MAP.get(int(scoring_info.mSession), "unknown")
        self._track_length_m = float(scoring_info.mLapDist) if scoring_info.mLapDist > 0 else 0.0
        self._driver_name = self._decode_text(scoring_info.mPlayerName)
        self._game_version = int(layout.data.generic.gameVersion)

        if player_telem is not None:
            self._car_name = self._decode_text(player_telem.mVehicleName) or self._car_name
            if player_telem.mFuelCapacity > 0:
                self._fuel_capacity = float(player_telem.mFuelCapacity)
        elif player_scoring is not None:
            self._car_name = self._decode_text(player_scoring.mVehicleName) or self._car_name

    def _get_player_telemetry(self, layout: SharedMemoryLayout) -> TelemInfoV01 | None:
        telemetry = layout.data.telemetry
        if not telemetry.playerHasVehicle:
            return None
        idx = int(telemetry.playerVehicleIdx)
        active = min(int(telemetry.activeVehicles), MAX_VEHICLES)
        if 0 <= idx < active:
            return telemetry.telemInfo[idx]
        return None

    def read_relative(self) -> dict[str, Any] | None:
        """Extract gap to car ahead/behind from LMU shared memory.

        Uses VehicleScoringInfoV01.mTimeBehindNext. For the car ahead,
        that's the player's own mTimeBehindNext (gap to the car one
        place in front). For the car behind, find the car whose mPlace
        is player_place + 1 and read ITS mTimeBehindNext.
        """
        layout = self._layout
        if layout is None:
            return None
        try:
            scoring = layout.data.scoring
            count = max(0, min(int(scoring.scoringInfo.mNumVehicles), MAX_VEHICLES))
            vehicles = scoring.vehScoringInfo
            player = self._get_player_scoring(layout)
            if player is None:
                return None
            player_place = int(player.mPlace)
        except Exception:
            return None

        result: dict[str, Any] = {}

        # Car ahead: player's mTimeBehindNext (skip if lapped or on pit)
        if player_place > 1:
            gap_ahead = float(player.mTimeBehindNext)
            laps_behind = int(player.mLapsBehindNext)
            if 0 < gap_ahead < 300 and laps_behind == 0 and not bool(player.mInPits):
                result["gap_ahead_s"] = round(gap_ahead, 3)
                result["position_ahead"] = player_place - 1

        # Car behind: find the vehicle with mPlace == player_place + 1
        for idx in range(count):
            v = vehicles[idx]
            if int(v.mPlace) == player_place + 1:
                gap_behind = float(v.mTimeBehindNext)
                laps_behind = int(v.mLapsBehindNext)
                if 0 < gap_behind < 300 and laps_behind == 0 and not bool(v.mInPits):
                    result["gap_behind_s"] = round(gap_behind, 3)
                    result["position_behind"] = player_place + 1
                break

        return result or None

    def _get_player_scoring(
        self,
        layout: SharedMemoryLayout,
        *,
        telem_id: int | None = None,
    ) -> VehicleScoringInfoV01 | None:
        count = max(0, min(int(layout.data.scoring.scoringInfo.mNumVehicles), MAX_VEHICLES))
        vehicles = layout.data.scoring.vehScoringInfo
        for idx in range(count):
            if bool(vehicles[idx].mIsPlayer):
                return vehicles[idx]
        if telem_id is not None:
            for idx in range(count):
                if int(vehicles[idx].mID) == telem_id:
                    return vehicles[idx]
        player_idx = int(layout.data.telemetry.playerVehicleIdx)
        if 0 <= player_idx < count:
            return vehicles[player_idx]
        return None

    def _close_mapping(self) -> None:
        if self._shm is not None:
            try:
                self._shm.close()
            except Exception:
                pass
            self._shm = None

    @staticmethod
    def _meters_to_g(value: float) -> float | None:
        if math.isnan(value) or math.isinf(value):
            return None
        return value / _G_MPS2

    @staticmethod
    def _kelvin_to_c(value: float) -> float | None:
        if math.isnan(value) or math.isinf(value):
            return None
        return value - 273.15 if value > 150.0 else value

    @staticmethod
    def _is_in_pits(player_scoring: VehicleScoringInfoV01 | None) -> bool | None:
        if player_scoring is None:
            return None
        return bool(player_scoring.mInPits or int(player_scoring.mPitState) in _PIT_STATES)

    @staticmethod
    def _decode_text(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray)):
            text = bytes(value).split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()
            return text or None
        if isinstance(value, str):
            text = value.split("\x00", 1)[0].strip()
            return text or None
        return str(value).strip() or None

    @classmethod
    def _flatten_struct(cls, struct_obj: ctypes.Structure, prefix: str, out: dict[str, Any]) -> None:
        for field_name, _ in getattr(struct_obj, "_fields_", []):
            if field_name.startswith("mExpansion") or field_name.startswith("mUnused"):
                continue
            if field_name in {"mVehicle", "mResultsStream", "mAppWindow"}:
                continue
            cls._flatten_value(f"{prefix}__{field_name}", getattr(struct_obj, field_name), out)

    @classmethod
    def _flatten_value(cls, prefix: str, value: Any, out: dict[str, Any]) -> None:
        if isinstance(value, ctypes.Structure):
            cls._flatten_struct(value, prefix, out)
            return
        if isinstance(value, ctypes.Array):
            for idx, item in enumerate(value):
                cls._flatten_value(f"{prefix}__{idx}", item, out)
            return
        out[prefix] = cls._safe_raw_value(value)

    @classmethod
    def _struct_to_dict(cls, struct_obj: ctypes.Structure | None) -> dict[str, Any] | None:
        if struct_obj is None:
            return None
        data: dict[str, Any] = {}
        for field_name, _ in getattr(struct_obj, "_fields_", []):
            if field_name.startswith("mExpansion"):
                continue
            if field_name in {"mVehicle", "mResultsStream", "mAppWindow"}:
                continue
            data[field_name] = cls._to_python(getattr(struct_obj, field_name))
        return data

    @classmethod
    def _to_python(cls, value: Any) -> Any:
        if isinstance(value, ctypes.Structure):
            return cls._struct_to_dict(value)
        if isinstance(value, ctypes.Array):
            return [cls._to_python(item) for item in value]
        return cls._safe_raw_value(value)

    @classmethod
    def _safe_raw_value(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray)):
            return cls._decode_text(value)
        if isinstance(value, float):
            return None if math.isnan(value) or math.isinf(value) else value
        if isinstance(value, (int, bool, str)):
            return value
        return str(value)


def _clean_float(value: object) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        return None
    if number <= 0:
        return None
    return number


def _normalize_percent(value: object) -> float | None:
    number = _clean_float(value)
    if number is None:
        return None
    if 0.0 <= number <= 1.0:
        return round(number * 100.0, 2)
    return round(number, 2)


def _lmu_sector_index(value: int) -> int | None:
    if value <= 0:
        return 1
    return min(3, value)


def _lmu_session_status(game_phase: object) -> str | None:
    if not isinstance(game_phase, int):
        return None
    if game_phase == 5:
        return "green_flag"
    if game_phase == 6:
        return "full_course_yellow"
    if game_phase == 8:
        return "session_over"
    return f"phase_{game_phase}"


def _lmu_flag_state(yellow_flag_state: object, player_scoring: VehicleScoringInfoV01 | None) -> str | None:
    if isinstance(yellow_flag_state, int) and yellow_flag_state > 0:
        return "yellow"
    if player_scoring is None:
        return None
    if bool(player_scoring.mUnderYellow):
        return "yellow"
    if int(player_scoring.mFlag) > 0:
        return f"flag_{int(player_scoring.mFlag)}"
    return "green" if not bool(player_scoring.mInPits) else None
