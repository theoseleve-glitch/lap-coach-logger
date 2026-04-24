"""iRacing telemetry adapter – full-capture implementation.

Uses the ``pyirsdk`` library to read iRacing's memory-mapped telemetry
data.  If pyirsdk is not installed (e.g. on a dev machine without
iRacing) the adapter falls back to a safe no-op mode and logs a
warning at startup.

Session activity is determined by reading the ``IsOnTrack`` variable
from iRacing's shared memory — this avoids false starts from menus,
replays, and loading screens.

This adapter supports two capture modes:
  - **Normalized** (``read_sample``): the original hand-picked var set
    mapped to the cross-sim ``TelemetrySample`` schema.
  - **Raw** (``read_raw_sample``): every public IRSDK variable, with
    array vars flattened into deterministic suffixed columns.

The sampling loop is tick-driven in ``auto_sdk`` mode: it waits for
the IRSDK buffer tick to change rather than sleeping a fixed interval.
"""

from __future__ import annotations

import logging
import math
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from lap_coach_logger.adapters.base import SimAdapter
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.normalization.mapper import normalise_sample

log = logging.getLogger(__name__)

# Process names iRacing may appear as
_IRACING_EXES = ["iRacingSim64DX11.exe", "iRacingSim.exe"]

# Try to import pyirsdk; if unavailable the adapter will be inert
try:
    import irsdk

    _HAS_IRSDK = True
except ImportError:
    _HAS_IRSDK = False
    log.info("pyirsdk not installed – iRacing adapter will be inert")

# iRacing session state constants (from irsdk)
_IRSDK_STATE_INVALID = 0

# Prefix for flattened raw IRSDK columns
_RAW_PREFIX = "irsdk__"


class IRacingAdapter(SimAdapter):
    """Adapter for iRacing via pyirsdk shared-memory API."""

    def __init__(self) -> None:
        self._connected: bool = False
        self._session_uid: str = ""
        self._ir: object | None = None  # irsdk.IRSDK instance
        # Cached metadata (read once per session from session info YAML)
        self._track_name: str | None = None
        self._car_name: str | None = None
        self._session_type: str | None = None
        self._fuel_capacity: float | None = None
        # Tick-driven sampling state
        self._last_buffer_tick: int | None = None
        self._sdk_tick_rate_hz: int | None = None
        self._session_info_update: int | None = None
        # Var header cache (built once per connection)
        self._var_headers: list[dict[str, Any]] | None = None

    # -- SimAdapter interface -----------------------------------------------

    @property
    def sim_name(self) -> str:
        return "iRacing"

    @property
    def process_names(self) -> list[str]:
        return list(_IRACING_EXES)

    def connect(self) -> bool:
        if not _HAS_IRSDK:
            log.warning("pyirsdk unavailable – cannot connect to iRacing")
            return False

        try:
            ir = irsdk.IRSDK()  # type: ignore[attr-defined]
            if not ir.startup():
                log.info("iRacing shared memory not available yet")
                return False

            self._ir = ir
            self._connected = True
            self._session_uid = uuid.uuid4().hex[:12]
            self._last_buffer_tick = None
            self._session_info_update = None
            self._read_session_metadata()
            self._cache_var_headers()
            self._read_sdk_tick_rate()
            log.info(
                "iRacing adapter connected: track=%s car=%s session=%s uid=%s tick_rate=%s",
                self._track_name,
                self._car_name,
                self._session_type,
                self._session_uid,
                self._sdk_tick_rate_hz,
            )
            return True
        except Exception:
            log.exception("Failed to connect to iRacing shared memory")
            return False

    def disconnect(self) -> None:
        log.info("iRacing adapter: disconnecting")
        if self._ir is not None:
            try:
                self._ir.shutdown()  # type: ignore[union-attr]
            except Exception:
                log.debug("irsdk shutdown error (harmless)", exc_info=True)
        self._ir = None
        self._connected = False
        self._track_name = None
        self._car_name = None
        self._session_type = None
        self._var_headers = None
        self._last_buffer_tick = None
        self._sdk_tick_rate_hz = None
        self._session_info_update = None

    def is_session_active(self) -> bool:
        """Return True only when the driver is on track (not in menus/replay)."""
        if not self._connected or self._ir is None:
            return False
        try:
            ir = self._ir
            is_on_track = ir["IsOnTrack"]  # type: ignore[index]
            if is_on_track is None:
                return False
            return bool(is_on_track)
        except Exception:
            return False

    def read_sample(self) -> TelemetrySample | None:
        if not self._connected or self._ir is None:
            return None

        ir = self._ir
        try:
            ir.freeze_var_buffer_latest()  # type: ignore[union-attr]

            raw = {
                "SessionTime": self._get_float(ir, "SessionTime"),
                "Lap": self._get_int(ir, "Lap"),
                "LapDist": self._get_float(ir, "LapDist"),
                "LapDistPct": self._get_float(ir, "LapDistPct"),
                "Speed": self._get_float(ir, "Speed"),
                "Throttle": self._get_float(ir, "Throttle"),
                "Brake": self._get_float(ir, "Brake"),
                "SteeringWheelAngle": self._get_float(ir, "SteeringWheelAngle"),
                "Clutch": self._get_float(ir, "Clutch"),
                "Gear": self._get_int(ir, "Gear"),
                "RPM": self._get_float(ir, "RPM"),
                "Lat": self._get_float(ir, "Lat"),
                "Alt": self._get_float(ir, "Alt"),
                "Lon": self._get_float(ir, "Lon"),
                "Yaw": self._get_float(ir, "Yaw"),
                "Pitch": self._get_float(ir, "Pitch"),
                "Roll": self._get_float(ir, "Roll"),
                "LongAccel": self._get_float(ir, "LongAccel"),
                "LatAccel": self._get_float(ir, "LatAccel"),
                "LFtempCL": self._get_float(ir, "LFtempCL"),
                "RFtempCL": self._get_float(ir, "RFtempCL"),
                "LRtempCL": self._get_float(ir, "LRtempCL"),
                "RRtempCL": self._get_float(ir, "RRtempCL"),
                "FuelLevel": self._get_float(ir, "FuelLevel"),
                "WaterTemp": self._get_float(ir, "WaterTemp"),
                "OilTemp": self._get_float(ir, "OilTemp"),
                "TrackTempCrew": self._get_float(ir, "TrackTempCrew"),
                "AirTemp": self._get_float(ir, "AirTemp"),
                "IsOnTrack": self._get_bool(ir, "IsOnTrack"),
                "OnPitRoad": self._get_bool(ir, "OnPitRoad"),
                "dcABS": self._get_float(ir, "dcABS"),
                "dcTractionControl": self._get_float(ir, "dcTractionControl"),
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
                },
            )
        except Exception:
            log.debug("Error reading iRacing sample", exc_info=True)
            return None

    def read_dashboard_state(self) -> dict[str, Any] | None:
        if not self._connected or self._ir is None:
            return None

        ir = self._ir
        try:
            ir.freeze_var_buffer_latest()  # type: ignore[union-attr]
            return {
                "lap_time_s": self._get_float(ir, "LapCurrentLapTime"),
                "last_lap_time_s": self._get_float(ir, "LapLastLapTime"),
                "best_lap_time_s": self._get_float(ir, "LapBestLapTime"),
                "live_delta_s": _first_float(
                    self._get_float(ir, "LapDeltaToBestLap"),
                    self._get_float(ir, "LapDeltaToSessionBestLap"),
                ),
                "current_sector_index": self._get_int(ir, "LapCurrentSector"),
                "fuel_level": self._get_float(ir, "FuelLevel"),
                "session_status": (
                    "pit_road"
                    if self._get_bool(ir, "OnPitRoad")
                    else ("on_track" if self._get_bool(ir, "IsOnTrack") else None)
                ),
                "flag_state": _iracing_flag_state(self._get_int(ir, "SessionFlags")),
                "tyre_pressure_lf": self._get_float(ir, "LFpressure"),
                "tyre_pressure_rf": self._get_float(ir, "RFpressure"),
                "tyre_pressure_lr": self._get_float(ir, "LRpressure"),
                "tyre_pressure_rr": self._get_float(ir, "RRpressure"),
                "tyre_temp_lf": _first_float(self._get_float(ir, "LFtempCL"), self._get_float(ir, "LFtempCM")),
                "tyre_temp_rf": _first_float(self._get_float(ir, "RFtempCL"), self._get_float(ir, "RFtempCM")),
                "tyre_temp_lr": _first_float(self._get_float(ir, "LRtempCL"), self._get_float(ir, "LRtempCM")),
                "tyre_temp_rr": _first_float(self._get_float(ir, "RRtempCL"), self._get_float(ir, "RRtempCM")),
                "tyre_wear_lf": _first_float(self._get_float(ir, "LFwearM"), self._get_float(ir, "LFwearL")),
                "tyre_wear_rf": _first_float(self._get_float(ir, "RFwearM"), self._get_float(ir, "RFwearL")),
                "tyre_wear_lr": _first_float(self._get_float(ir, "LRwearM"), self._get_float(ir, "LRwearL")),
                "tyre_wear_rr": _first_float(self._get_float(ir, "RRwearM"), self._get_float(ir, "RRwearL")),
                "brake_temp_lf": self._get_float(ir, "LFbrakeTemp"),
                "brake_temp_rf": self._get_float(ir, "RFbrakeTemp"),
                "brake_temp_lr": self._get_float(ir, "LRbrakeTemp"),
                "brake_temp_rr": self._get_float(ir, "RRbrakeTemp"),
                "tc_level": self._get_float(ir, "dcTractionControl"),
                "abs_level": self._get_float(ir, "dcABS"),
                "engine_map": _first_float(self._get_float(ir, "dcFuelMixture"), self._get_float(ir, "dcEnginePower")),
                "brake_bias_pct": self._get_float(ir, "dcBrakeBias"),
            }
        except Exception:
            log.debug("Error reading iRacing dashboard state", exc_info=True)
            return None

    @property
    def connected(self) -> bool:
        return self._connected

    # -- relative/gap data (iRacing first-class) ---------------------------

    def read_relative(self) -> dict[str, Any] | None:
        """Extract gap to car ahead/behind from iRacing SDK.

        Data sources:
          - PlayerCarIdx: the driver's car index in CarIdx* arrays
          - CarIdxClassPosition: 1-based class position per car
          - CarIdxF2Time: delta-to-leader per car (seconds); subtract to
            get pairwise gap
          - CarIdxLapDistPct / CarIdxOnPitRoad: used to filter
            neighbours that are on pit road (gap would be meaningless)

        Returns None only when SDK is disconnected; returns partial dict
        (missing keys) when some neighbours can't be identified.
        """
        if not self._connected or self._ir is None:
            return None
        ir = self._ir
        try:
            player_idx = ir["PlayerCarIdx"]  # type: ignore[index]
            class_positions = ir["CarIdxClassPosition"]  # type: ignore[index]
            f2_times = ir["CarIdxF2Time"]  # type: ignore[index]
            on_pit = ir["CarIdxOnPitRoad"]  # type: ignore[index]
        except Exception:
            return None

        if player_idx is None or class_positions is None or f2_times is None:
            return None
        if not (0 <= int(player_idx) < len(class_positions)):
            return None

        player_class_pos = int(class_positions[player_idx])
        player_f2 = float(f2_times[player_idx]) if f2_times[player_idx] is not None else None
        if player_class_pos <= 0 or player_f2 is None:
            return None

        # Find neighbours by class position — closest car ahead and behind
        ahead_idx: int | None = None
        behind_idx: int | None = None
        ahead_gap_class_pos = 10_000
        behind_gap_class_pos = 10_000

        for idx, pos in enumerate(class_positions):
            try:
                p = int(pos)
            except (TypeError, ValueError):
                continue
            if idx == int(player_idx) or p <= 0:
                continue
            if on_pit is not None and idx < len(on_pit) and bool(on_pit[idx]):
                continue  # skip cars in pit lane — gap isn't meaningful
            delta_pos = player_class_pos - p
            if delta_pos > 0 and delta_pos < ahead_gap_class_pos:
                ahead_gap_class_pos = delta_pos
                ahead_idx = idx
            elif delta_pos < 0 and -delta_pos < behind_gap_class_pos:
                behind_gap_class_pos = -delta_pos
                behind_idx = idx

        result: dict[str, Any] = {}

        if ahead_idx is not None and f2_times[ahead_idx] is not None:
            gap = player_f2 - float(f2_times[ahead_idx])
            if gap > 0 and gap < 300:  # sanity: skip lapped / ghost cars
                result["gap_ahead_s"] = round(gap, 3)
                result["position_ahead"] = int(class_positions[ahead_idx])

        if behind_idx is not None and f2_times[behind_idx] is not None:
            gap = float(f2_times[behind_idx]) - player_f2
            if gap > 0 and gap < 300:
                result["gap_behind_s"] = round(gap, 3)
                result["position_behind"] = int(class_positions[behind_idx])

        return result or None

    # -- extended capture interface -----------------------------------------

    def supports_raw_capture(self) -> bool:
        return True

    def wait_for_new_tick(self, timeout_s: float = 1.0) -> bool:
        """Block until the IRSDK buffer tick changes, signalling fresh data.

        Uses a tight poll-wait on the buffer tick rather than a fixed
        sleep.  Returns True if a new tick was observed, False on timeout.
        """
        if not self._connected or self._ir is None:
            return False

        ir = self._ir
        deadline = time.monotonic() + timeout_s
        # Poll interval: 0.5 ms to stay well under the expected tick period
        poll_interval = 0.0005

        while time.monotonic() < deadline:
            try:
                ir.freeze_var_buffer_latest()  # type: ignore[union-attr]
                tick = self._read_buffer_tick(ir)
                if tick is not None and tick != self._last_buffer_tick:
                    self._last_buffer_tick = tick
                    return True
            except Exception:
                return False
            time.sleep(poll_interval)

        return False

    def read_raw_sample(self) -> dict[str, Any] | None:
        """Read all public IRSDK vars into a flat dict.

        Scalar vars → ``irsdk__VarName``
        Array vars  → ``irsdk__VarName__0``, ``irsdk__VarName__1``, …

        Also includes runtime metadata fields.
        """
        if not self._connected or self._ir is None:
            return None

        ir = self._ir
        try:
            ir.freeze_var_buffer_latest()  # type: ignore[union-attr]
            row: dict[str, Any] = {}

            if self._var_headers:
                for vh in self._var_headers:
                    name = vh["name"]
                    count = vh["count"]
                    try:
                        val = ir[name]  # type: ignore[index]
                    except Exception:
                        val = None

                    if count == 1:
                        row[f"{_RAW_PREFIX}{name}"] = _safe_value(val)
                    else:
                        # Array var: flatten to suffixed columns
                        if isinstance(val, (list, tuple)):
                            for i, v in enumerate(val):
                                row[f"{_RAW_PREFIX}{name}__{i}"] = _safe_value(v)
                            # Pad if val shorter than declared count
                            for i in range(len(val), count):
                                row[f"{_RAW_PREFIX}{name}__{i}"] = None
                        else:
                            # Unexpected scalar for array var — store in element 0
                            row[f"{_RAW_PREFIX}{name}__0"] = _safe_value(val)
                            for i in range(1, count):
                                row[f"{_RAW_PREFIX}{name}__{i}"] = None

            # Runtime metadata
            row[f"{_RAW_PREFIX}header_tick_rate_hz"] = self._sdk_tick_rate_hz
            row[f"{_RAW_PREFIX}header_num_buf"] = self._read_num_buf(ir)
            row[f"{_RAW_PREFIX}var_buffer_tick"] = self._last_buffer_tick
            row[f"{_RAW_PREFIX}session_info_update"] = self._read_session_info_update(ir)
            row[f"{_RAW_PREFIX}sample_timestamp_utc"] = datetime.now(timezone.utc).isoformat()

            return row

        except Exception:
            log.debug("Error reading iRacing raw sample", exc_info=True)
            return None

    def read_session_info_snapshot(self) -> dict[str, Any] | None:
        """Flatten the entire IRSDK session-info YAML tree.

        Keys are flattened with ``__`` separators:
          ``WeekendInfo.TrackName`` → ``session__WeekendInfo__TrackName``
          ``SessionInfo.Sessions[0].SessionType`` → ``session__SessionInfo__Sessions__0__SessionType``
        """
        if not self._connected or self._ir is None:
            return None

        ir = self._ir
        try:
            # Force a parse of the latest session info string
            # pyirsdk caches session_info as a parsed dict
            session_info_dict = None
            if hasattr(ir, "_session_info") and ir._session_info:  # type: ignore[union-attr]
                session_info_dict = ir._session_info  # type: ignore[union-attr]

            if session_info_dict is None:
                # Try forcing parse
                try:
                    ir.parse_to(ir._parse_to_sec)  # type: ignore[union-attr]
                except Exception:
                    pass
                if hasattr(ir, "_session_info") and ir._session_info:  # type: ignore[union-attr]
                    session_info_dict = ir._session_info  # type: ignore[union-attr]

            if session_info_dict is None:
                return None

            flat: dict[str, Any] = {}
            _flatten_dict(session_info_dict, "session", flat)
            return flat

        except Exception:
            log.debug("Error reading iRacing session info snapshot", exc_info=True)
            return None

    def get_sdk_metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "sdk_tick_rate_hz": self._sdk_tick_rate_hz,
            "session_uid": self._session_uid,
            "track_name": self._track_name,
            "car_name": self._car_name,
            "session_type": self._session_type,
        }
        if self._ir is not None:
            meta["header_num_buf"] = self._read_num_buf(self._ir)
        return meta

    # -- internals ----------------------------------------------------------

    def _read_session_metadata(self) -> None:
        """Extract track/car/session from the session-info YAML (cached)."""
        if self._ir is None:
            return
        try:
            ir = self._ir
            weekend = ir["WeekendInfo"]  # type: ignore[index]
            if weekend:
                self._track_name = weekend.get("TrackDisplayName") or weekend.get("TrackName")

            driver_info = ir["DriverInfo"]  # type: ignore[index]
            if driver_info:
                drivers = driver_info.get("Drivers", [])
                driver_idx = driver_info.get("DriverCarIdx", 0)
                for d in drivers:
                    if d.get("CarIdx") == driver_idx:
                        self._car_name = d.get("CarScreenName") or d.get("CarPath")
                        break
                fuel_max = driver_info.get("DriverCarFuelMaxLtr")
                if fuel_max is not None:
                    try:
                        self._fuel_capacity = float(fuel_max)
                    except (ValueError, TypeError):
                        pass

            session_info = ir["SessionInfo"]  # type: ignore[index]
            if session_info:
                sessions = session_info.get("Sessions", [])
                session_num = ir["SessionNum"]  # type: ignore[index]
                if session_num is not None and 0 <= session_num < len(sessions):
                    self._session_type = sessions[session_num].get("SessionType", "unknown")

        except Exception:
            log.debug("Could not read iRacing session metadata", exc_info=True)

    def _cache_var_headers(self) -> None:
        """Build a list of var header dicts from the IRSDK shared-memory header."""
        if self._ir is None:
            self._var_headers = None
            return

        ir = self._ir
        try:
            headers: list[dict[str, Any]] = []
            # pyirsdk exposes var_headers_names as a dict of VarHeader objects
            if hasattr(ir, "var_headers_names") and ir.var_headers_names:  # type: ignore[union-attr]
                for name, vh_obj in ir.var_headers_names.items():  # type: ignore[union-attr]
                    count = getattr(vh_obj, "count", 1) or 1
                    headers.append({"name": name, "count": count})
            self._var_headers = sorted(headers, key=lambda h: h["name"])
            log.info("Cached %d IRSDK var headers", len(self._var_headers))
        except Exception:
            log.debug("Could not cache IRSDK var headers", exc_info=True)
            self._var_headers = None

    def _read_sdk_tick_rate(self) -> None:
        """Read the SDK header tick_rate — the real publish cadence."""
        if self._ir is None:
            return
        ir = self._ir
        try:
            # pyirsdk exposes the header as ._header
            hdr = getattr(ir, "_header", None)
            if hdr is not None:
                tick_rate = getattr(hdr, "tick_rate", None)
                if tick_rate is not None and int(tick_rate) > 0:
                    self._sdk_tick_rate_hz = int(tick_rate)
                    return
            # Fallback: read from shared memory directly if available
            if hasattr(ir, "header") and ir.header:  # type: ignore[union-attr]
                tick_rate = getattr(ir.header, "tick_rate", None)  # type: ignore[union-attr]
                if tick_rate is not None and int(tick_rate) > 0:
                    self._sdk_tick_rate_hz = int(tick_rate)
                    return
        except Exception:
            log.debug("Could not read SDK tick rate", exc_info=True)

    @staticmethod
    def _read_buffer_tick(ir: object) -> int | None:
        """Read the current variable buffer tick count."""
        try:
            hdr = getattr(ir, "_header", None) or getattr(ir, "header", None)
            if hdr is None:
                return None
            # The buffer tick is in the var_buf array
            var_buf = getattr(hdr, "var_buf", None)
            if var_buf and len(var_buf) > 0:
                return int(var_buf[0].tick_count)
        except Exception:
            pass
        # Fallback: use SessionTick variable
        try:
            tick = ir["SessionTick"]  # type: ignore[index]
            return int(tick) if tick is not None else None
        except Exception:
            return None

    @staticmethod
    def _read_num_buf(ir: object) -> int | None:
        try:
            hdr = getattr(ir, "_header", None) or getattr(ir, "header", None)
            if hdr is not None:
                return int(getattr(hdr, "num_buf", 0))
        except Exception:
            pass
        return None

    @staticmethod
    def _read_session_info_update(ir: object) -> int | None:
        try:
            hdr = getattr(ir, "_header", None) or getattr(ir, "header", None)
            if hdr is not None:
                return int(getattr(hdr, "session_info_update", 0))
        except Exception:
            pass
        return None

    @staticmethod
    def _get_float(ir: object, key: str) -> float | None:
        try:
            val = ir[key]  # type: ignore[index]
            if val is None:
                return None
            f = float(val)
            return None if (f != f or f in (float("inf"), float("-inf"))) else f
        except Exception:
            return None

    @staticmethod
    def _get_int(ir: object, key: str) -> int | None:
        try:
            val = ir[key]  # type: ignore[index]
            return int(val) if val is not None else None
        except Exception:
            return None

    @staticmethod
    def _get_bool(ir: object, key: str) -> bool | None:
        try:
            val = ir[key]  # type: ignore[index]
            return bool(val) if val is not None else None
        except Exception:
            return None


# -- module-level helpers ---------------------------------------------------


def _safe_value(val: Any) -> Any:
    """Sanitise a raw SDK value for safe serialization."""
    if val is None:
        return None
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    if isinstance(val, (int, bool, str)):
        return val
    if isinstance(val, (list, tuple)):
        return [_safe_value(v) for v in val]
    # Fallback: convert to string
    return str(val)


def _flatten_dict(obj: Any, prefix: str, result: dict[str, Any]) -> None:
    """Recursively flatten a nested dict/list into ``prefix__key`` paths."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten_dict(v, f"{prefix}__{k}", result)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _flatten_dict(v, f"{prefix}__{i}", result)
    else:
        # Leaf value
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            result[prefix] = None
        else:
            result[prefix] = obj


def _first_float(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


def _iracing_flag_state(flags: int | None) -> str | None:
    if flags is None or flags <= 0 or not _HAS_IRSDK:
        return None
    try:
        if flags & int(irsdk.Flags.red):  # type: ignore[attr-defined]
            return "red"
        if flags & int(irsdk.Flags.checkered):  # type: ignore[attr-defined]
            return "checkered"
        if flags & int(irsdk.Flags.yellow_waving):  # type: ignore[attr-defined]
            return "yellow_waving"
        if flags & int(irsdk.Flags.yellow):  # type: ignore[attr-defined]
            return "yellow"
        if flags & int(irsdk.Flags.caution_waving):  # type: ignore[attr-defined]
            return "caution_waving"
        if flags & int(irsdk.Flags.caution):  # type: ignore[attr-defined]
            return "caution"
        if flags & int(irsdk.Flags.white):  # type: ignore[attr-defined]
            return "white"
        if flags & int(irsdk.Flags.green):  # type: ignore[attr-defined]
            return "green"
    except Exception:
        return f"flags_{flags}"
    return f"flags_{flags}"
