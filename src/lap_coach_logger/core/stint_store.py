"""Stint data persistence and per-compound profile aggregation.

Accumulates stint records across sessions, keyed by "track::car".
More laps logged yields better weighted averages and higher confidence.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from lap_coach_logger.core.strategy_models import (
    LapObservation,
    PitMeasurement,
    PitProfile,
    StintLapSeries,
    fit_degradation_model,
    fit_pit_profile,
    fit_thermal_model,
    fit_warmup_model,
)

log = logging.getLogger(__name__)

# Reserved meta-keys in the on-disk data dict that are NOT track::car stint
# lists.  Anything matching these names is skipped by stint iteration.
_META_KEY_PIT_PROFILES = "_pit_profiles"


@dataclass
class StintRecord:
    """A single recorded stint."""

    compound: str
    fuel_per_lap: float
    fuel_per_lap_series: list[float]
    wear_per_lap: float
    grip_at_end: float
    lap_count: int
    avg_lap_time_s: float
    track_temp_c: float
    air_temp_c: float
    source_session_id: str
    source_label: str
    id: str = field(default_factory=lambda: uuid4().hex)
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    excluded: bool = False
    lap_times_s: list[float] = field(default_factory=list)
    lap_avg_temps_c: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "compound": self.compound,
            "fuel_per_lap": self.fuel_per_lap,
            "fuel_per_lap_series": list(self.fuel_per_lap_series),
            "wear_per_lap": self.wear_per_lap,
            "grip_at_end": self.grip_at_end,
            "lap_count": self.lap_count,
            "avg_lap_time_s": self.avg_lap_time_s,
            "track_temp_c": self.track_temp_c,
            "air_temp_c": self.air_temp_c,
            "source_session_id": self.source_session_id,
            "source_label": self.source_label,
            "recorded_at": self.recorded_at,
            "excluded": self.excluded,
            "lap_times_s": list(self.lap_times_s),
            "lap_avg_temps_c": list(self.lap_avg_temps_c),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StintRecord":
        return cls(
            id=str(d["id"]),
            compound=str(d["compound"]),
            fuel_per_lap=float(d["fuel_per_lap"]),
            fuel_per_lap_series=[float(v) for v in d.get("fuel_per_lap_series", [])],
            wear_per_lap=float(d["wear_per_lap"]),
            grip_at_end=float(d["grip_at_end"]),
            lap_count=int(d["lap_count"]),
            avg_lap_time_s=float(d["avg_lap_time_s"]),
            track_temp_c=float(d["track_temp_c"]),
            air_temp_c=float(d["air_temp_c"]),
            source_session_id=str(d.get("source_session_id", "")),
            source_label=str(d.get("source_label", "")),
            recorded_at=str(d.get("recorded_at", "")),
            excluded=bool(d.get("excluded", False)),
            lap_times_s=[float(v) for v in d.get("lap_times_s", [])],
            lap_avg_temps_c=[float(v) for v in d.get("lap_avg_temps_c", [])],
        )


@dataclass
class CompoundProfile:
    """Aggregated profile for one tire compound on a track/car combo."""

    compound: str
    fuel_per_lap: float
    fuel_curve: list[float]
    wear_per_lap: float
    estimated_life: int
    avg_lap_time_s: float
    lap_time_delta_s: float
    avg_track_temp_c: float
    total_laps_logged: int
    stint_count: int
    confidence: str  # "low" / "medium" / "high"
    thermal: dict | None = None
    warmup: dict | None = None
    degradation: dict | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "compound": self.compound,
            "fuel_per_lap": round(self.fuel_per_lap, 3),
            "fuel_curve": [round(v, 3) for v in self.fuel_curve],
            "wear_per_lap": round(self.wear_per_lap, 3),
            "estimated_life": self.estimated_life,
            "avg_lap_time_s": round(self.avg_lap_time_s, 3),
            "lap_time_delta_s": round(self.lap_time_delta_s, 3),
            "avg_track_temp_c": round(self.avg_track_temp_c, 1),
            "total_laps_logged": self.total_laps_logged,
            "stint_count": self.stint_count,
            "confidence": self.confidence,
            "thermal": self.thermal,
            "warmup": self.warmup,
            "degradation": self.degradation,
        }


def _make_key(track: str, car: str) -> str:
    return f"{track.strip().lower()}::{car.strip().lower()}"


class StintStore:
    """JSON-file-backed stint storage keyed by track::car.

    The underlying JSON file also stores a ``_pit_profiles`` meta entry
    (keyed by track name) containing lists of :class:`PitMeasurement`
    dicts used to fit per-track pit cost models.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, list[dict[str, Any]]] = {}
        self._pit_profiles: dict[str, list[dict[str, Any]]] = {}
        self._load()

    def log_stint(self, track: str, car: str, record: StintRecord) -> None:
        key = _make_key(track, car)
        self._data.setdefault(key, []).append(record.to_dict())
        self._save()

    def list_stints(self, track: str, car: str) -> list[StintRecord]:
        key = _make_key(track, car)
        if key == _META_KEY_PIT_PROFILES:
            return []
        return [StintRecord.from_dict(d) for d in self._data.get(key, [])]

    def get_profiles(self, track: str, car: str) -> dict[str, CompoundProfile]:
        stints = [s for s in self.list_stints(track, car) if not s.excluded]
        if not stints:
            return {}
        by_compound: dict[str, list[StintRecord]] = {}
        for s in stints:
            by_compound.setdefault(s.compound, []).append(s)
        profiles: dict[str, CompoundProfile] = {}
        for compound, records in by_compound.items():
            profiles[compound] = _aggregate(compound, records)
        return profiles

    def exclude_stint(self, stint_id: str) -> None:
        self._set_excluded(stint_id, True)

    def include_stint(self, stint_id: str) -> None:
        self._set_excluded(stint_id, False)

    def clear(self, track: str, car: str) -> None:
        key = _make_key(track, car)
        if key == _META_KEY_PIT_PROFILES:
            return
        if key in self._data:
            del self._data[key]
            self._save()

    # ------------------------------------------------------------------
    # Pit profile persistence
    # ------------------------------------------------------------------
    def log_pit_measurement(
        self, track: str, measurement: PitMeasurement,
    ) -> None:
        """Persist a :class:`PitMeasurement` under *track*."""
        track_key = track.strip().lower()
        self._pit_profiles.setdefault(track_key, []).append(measurement.to_dict())
        self._save()

    def get_pit_profile(self, track: str) -> PitProfile:
        """Return a fitted :class:`PitProfile` for *track*.

        Always returns a :class:`PitProfile`; when no measurements exist
        the returned profile has ``None`` betas and an empty measurement
        list.
        """
        track_key = track.strip().lower()
        raw = self._pit_profiles.get(track_key, [])
        measurements = [PitMeasurement.from_dict(d) for d in raw]
        return fit_pit_profile(track, measurements)

    def import_from_session(
        self, session_path: Path, compound: str,
    ) -> "StintRecord | None":
        """Extract stint data from a saved session bundle and persist it.

        Reads session.json, laps.json, and telemetry (parquet or csv) from
        *session_path* to build a StintRecord with computed fuel deltas,
        wear estimates, and temperature averages.
        """
        # -- 1. Read session.json ----------------------------------------
        session_json_path = session_path / "session.json"
        if not session_json_path.exists():
            log.warning("import_from_session: session.json not found in %s", session_path)
            return None
        try:
            session_meta = json.loads(session_json_path.read_text(encoding="utf-8"))
        except Exception:
            log.warning("import_from_session: failed to parse session.json")
            return None

        track_name: str = session_meta.get("track_name") or "unknown"
        car_name: str = session_meta.get("car_name") or "unknown"
        session_type: str = session_meta.get("session_type") or ""
        started_at_utc: str = session_meta.get("started_at_utc") or ""
        sample_count: int = session_meta.get("sample_count", 0)
        session_id: str = session_meta.get("session_id") or started_at_utc

        # -- 2. Read laps.json ------------------------------------------
        laps_data: list[dict[str, Any]] = []
        laps_path = session_path / "laps.json"
        if laps_path.exists():
            try:
                laps_data = json.loads(laps_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # -- 3. Read telemetry -------------------------------------------
        tel_dict: dict[str, list[Any]] | None = None

        parquet_path = session_path / "telemetry.parquet"
        csv_path = session_path / "telemetry.csv"

        if parquet_path.exists():
            try:
                import pyarrow.parquet as pq
                table = pq.read_table(parquet_path)
                tel_dict = table.to_pydict()
            except Exception:
                log.warning("import_from_session: failed to read parquet")
                tel_dict = None

        if tel_dict is None and csv_path.exists():
            try:
                with open(csv_path, encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                if rows:
                    tel_dict = {col: [] for col in rows[0]}
                    for row in rows:
                        for col in tel_dict:
                            val = row.get(col)
                            # Parse numeric values from CSV strings
                            if val is None or val == "" or val == "None":
                                tel_dict[col].append(None)
                            else:
                                try:
                                    tel_dict[col].append(float(val))
                                except (ValueError, TypeError):
                                    tel_dict[col].append(val)
            except Exception:
                log.warning("import_from_session: failed to read CSV")
                tel_dict = None

        if tel_dict is None:
            log.warning("import_from_session: no telemetry file found in %s", session_path)
            return None

        # -- 4. Extract per-lap metrics ---------------------------------
        lap_numbers = tel_dict.get("lap_number", [])
        fuel_levels = tel_dict.get("fuel_level", [])
        tyre_lf = tel_dict.get("tyre_temp_lf", [])
        tyre_rf = tel_dict.get("tyre_temp_rf", [])
        tyre_lr = tel_dict.get("tyre_temp_lr", [])
        tyre_rr = tel_dict.get("tyre_temp_rr", [])
        track_temps = tel_dict.get("track_temp_c", [])
        air_temps = tel_dict.get("air_temp_c", [])

        n_samples = len(lap_numbers)

        # Group indices by lap number
        laps_by_num: dict[int, list[int]] = {}
        for idx in range(n_samples):
            ln = lap_numbers[idx]
            if ln is None:
                continue
            ln_int = int(ln)
            laps_by_num.setdefault(ln_int, []).append(idx)

        sorted_laps = sorted(laps_by_num.keys())

        # Per-lap fuel deltas
        fuel_per_lap_series: list[float] = []
        for lap_num in sorted_laps:
            indices = laps_by_num[lap_num]
            first_idx = indices[0]
            last_idx = indices[-1]
            f_start = fuel_levels[first_idx] if first_idx < len(fuel_levels) else None
            f_end = fuel_levels[last_idx] if last_idx < len(fuel_levels) else None
            if f_start is not None and f_end is not None:
                delta = float(f_start) - float(f_end)
                if delta >= 0:
                    fuel_per_lap_series.append(delta)

        fuel_per_lap = (
            sum(fuel_per_lap_series) / len(fuel_per_lap_series)
            if fuel_per_lap_series
            else 0.0
        )

        # Per-lap average tyre temps for wear estimation
        wear_per_lap_values: list[float] = []
        for lap_num in sorted_laps:
            indices = laps_by_num[lap_num]
            temps: list[float] = []
            for idx in indices:
                for col in (tyre_lf, tyre_rf, tyre_lr, tyre_rr):
                    if idx < len(col) and col[idx] is not None:
                        temps.append(float(col[idx]))
            avg_temp = sum(temps) / len(temps) if temps else 80.0

            # Wear estimation (same formula as StintRecorder)
            base_wear = 2.0
            if avg_temp < 75.0:
                base_wear += (75.0 - avg_temp) * 0.3
            elif avg_temp > 100.0:
                base_wear += (avg_temp - 100.0) * 0.5
            wear_per_lap_values.append(base_wear)

        wear_per_lap = (
            sum(wear_per_lap_values) / len(wear_per_lap_values)
            if wear_per_lap_values
            else 2.0
        )

        lap_count = len(sorted_laps)

        # Grip at end (100% minus cumulative wear)
        grip_at_end = max(0.0, 100.0 - wear_per_lap * lap_count)

        # Average lap time from laps.json
        valid_times = [
            float(lap["lap_time_s"])
            for lap in laps_data
            if lap.get("lap_time_s") is not None
        ]
        avg_lap_time_s = (
            sum(valid_times) / len(valid_times) if valid_times else 0.0
        )

        # Overall temperature averages
        valid_track_temps = [
            float(v) for v in track_temps if v is not None
        ]
        track_temp_c = (
            sum(valid_track_temps) / len(valid_track_temps)
            if valid_track_temps
            else 0.0
        )

        valid_air_temps = [float(v) for v in air_temps if v is not None]
        air_temp_c = (
            sum(valid_air_temps) / len(valid_air_temps)
            if valid_air_temps
            else 0.0
        )

        # -- 5. Build StintRecord ----------------------------------------
        record = StintRecord(
            compound=compound,
            fuel_per_lap=fuel_per_lap,
            fuel_per_lap_series=fuel_per_lap_series,
            wear_per_lap=wear_per_lap,
            grip_at_end=grip_at_end,
            lap_count=lap_count,
            avg_lap_time_s=avg_lap_time_s,
            track_temp_c=track_temp_c,
            air_temp_c=air_temp_c,
            source_session_id=session_id,
            source_label=session_type,
        )

        # -- 6. Persist --------------------------------------------------
        self.log_stint(track_name, car_name, record)

        # -- 7. Return ---------------------------------------------------
        return record

    def _set_excluded(self, stint_id: str, value: bool) -> None:
        for key, records in self._data.items():
            if key == _META_KEY_PIT_PROFILES:
                continue
            for rec in records:
                if rec.get("id") == stint_id:
                    rec["excluded"] = value
                    self._save()
                    return

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(raw, dict):
            return
        # Split off the pit-profiles meta entry so it isn't treated as
        # a track::car stint list.
        pit_raw = raw.get(_META_KEY_PIT_PROFILES)
        if isinstance(pit_raw, dict):
            self._pit_profiles = {
                str(k): list(v) if isinstance(v, list) else []
                for k, v in pit_raw.items()
            }
        self._data = {
            k: v for k, v in raw.items() if k != _META_KEY_PIT_PROFILES
        }

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        if self._pit_profiles:
            data[_META_KEY_PIT_PROFILES] = self._pit_profiles
        for key, records in self._data.items():
            data[key] = records
        self._path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )


def _aggregate(compound: str, records: list[StintRecord]) -> CompoundProfile:
    total_laps = sum(r.lap_count for r in records)
    stint_count = len(records)
    fuel_per_lap = sum(r.fuel_per_lap * r.lap_count for r in records) / total_laps
    wear_per_lap = sum(r.wear_per_lap * r.lap_count for r in records) / total_laps
    avg_lap_time = sum(r.avg_lap_time_s * r.lap_count for r in records) / total_laps
    avg_track_temp = sum(r.track_temp_c * r.lap_count for r in records) / total_laps
    fuel_curve = _average_fuel_curve(records)
    estimated_life = int((100 - 40) / wear_per_lap) if wear_per_lap > 0 else 999
    lap_times = [r.avg_lap_time_s for r in records]
    lap_time_delta = max(lap_times) - min(lap_times) if len(lap_times) > 1 else 0.0
    if total_laps >= 30:
        confidence = "high"
    elif total_laps >= 10:
        confidence = "medium"
    else:
        confidence = "low"

    # ------------------------------------------------------------------
    # Fit data-driven strategy models from per-lap observations.
    # Any fit function returns None when the input is insufficient.
    # ------------------------------------------------------------------
    all_laps: list[LapObservation] = []
    stint_series: list[StintLapSeries] = []
    for rec in records:
        if not rec.lap_times_s or not rec.lap_avg_temps_c:
            continue
        min_len = min(len(rec.lap_times_s), len(rec.lap_avg_temps_c))
        stint_laps: list[LapObservation] = []
        for i in range(min_len):
            lap = LapObservation(
                avg_tyre_temp_c=rec.lap_avg_temps_c[i],
                lap_time_s=rec.lap_times_s[i],
                stint_lap_index=i,
            )
            all_laps.append(lap)
            stint_laps.append(lap)
        if stint_laps:
            stint_series.append(StintLapSeries(laps=stint_laps))

    thermal_model = fit_thermal_model(all_laps)
    warmup_model = fit_warmup_model(stint_series)
    degradation_model = fit_degradation_model(all_laps)

    return CompoundProfile(
        compound=compound,
        fuel_per_lap=fuel_per_lap,
        fuel_curve=fuel_curve,
        wear_per_lap=wear_per_lap,
        estimated_life=estimated_life,
        avg_lap_time_s=avg_lap_time,
        lap_time_delta_s=lap_time_delta,
        avg_track_temp_c=avg_track_temp,
        total_laps_logged=total_laps,
        stint_count=stint_count,
        confidence=confidence,
        thermal=thermal_model.to_dict() if thermal_model else None,
        warmup=warmup_model.to_dict() if warmup_model else None,
        degradation=degradation_model.to_dict() if degradation_model else None,
    )


def _average_fuel_curve(records: list[StintRecord]) -> list[float]:
    """Average per-lap fuel deltas across stints."""
    series_list = [r.fuel_per_lap_series for r in records if r.fuel_per_lap_series]
    if not series_list:
        return []
    max_len = max(len(s) for s in series_list)
    curve: list[float] = []
    for i in range(max_len):
        values = [s[i] for s in series_list if i < len(s)]
        curve.append(sum(values) / len(values))
    return curve
