"""Stint data persistence and per-compound profile aggregation.

Accumulates stint records across sessions, keyed by "track::car".
More laps logged yields better weighted averages and higher confidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


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
        }


def _make_key(track: str, car: str) -> str:
    return f"{track.strip().lower()}::{car.strip().lower()}"


class StintStore:
    """JSON-file-backed stint storage keyed by track::car."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, list[dict[str, Any]]] = {}
        self._load()

    def log_stint(self, track: str, car: str, record: StintRecord) -> None:
        key = _make_key(track, car)
        self._data.setdefault(key, []).append(record.to_dict())
        self._save()

    def list_stints(self, track: str, car: str) -> list[StintRecord]:
        key = _make_key(track, car)
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
        if key in self._data:
            del self._data[key]
            self._save()

    def _set_excluded(self, stint_id: str, value: bool) -> None:
        for records in self._data.values():
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
        if isinstance(raw, dict):
            self._data = raw

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, indent=2),
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
