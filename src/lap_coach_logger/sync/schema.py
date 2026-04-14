"""Sync payload schemas — strict contracts for webapp communication.

Every sync payload is validated before queueing. No partial or
malformed data reaches the wire.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class SessionPayload:
    session_id: str
    sim: str
    track: str
    car: str
    mode: str           # sprint / endurance / coaching / data
    start_time: str     # ISO 8601
    end_time: str       # ISO 8601
    sample_count: int = 0
    driver_name: str = ""

    def validate(self) -> list[str]:
        errors = []
        if not self.session_id:
            errors.append("session_id is required")
        if not self.sim:
            errors.append("sim is required")
        if not self.track:
            errors.append("track is required")
        if not self.car:
            errors.append("car is required")
        if self.mode not in ("sprint", "endurance", "coaching", "data"):
            errors.append(f"invalid mode: {self.mode}")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "sim": self.sim,
            "track": self.track,
            "car": self.car,
            "mode": self.mode,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "sample_count": self.sample_count,
            "driver_name": self.driver_name,
        }


@dataclass
class LapPayload:
    session_id: str
    lap_number: int
    lap_time_s: float
    valid: bool
    fuel_used_l: float
    sector_times_s: list[float] = field(default_factory=list)
    consistency_pct: float | None = None
    std_dev_s: float | None = None

    def validate(self) -> list[str]:
        errors = []
        if not self.session_id:
            errors.append("session_id is required")
        if self.lap_number < 0:
            errors.append("lap_number must be >= 0")
        if self.lap_time_s <= 0:
            errors.append("lap_time_s must be > 0")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "lap_number": self.lap_number,
            "lap_time_s": round(self.lap_time_s, 3),
            "valid": self.valid,
            "fuel_used_l": round(self.fuel_used_l, 3),
            "sector_times_s": [round(t, 3) for t in self.sector_times_s],
            "consistency_pct": round(self.consistency_pct, 1) if self.consistency_pct is not None else None,
            "std_dev_s": round(self.std_dev_s, 3) if self.std_dev_s is not None else None,
        }


@dataclass
class CoachingPayload:
    session_id: str
    consistency_score: float
    trend: str
    focus_area: str
    recommendation: str
    confidence: str     # high / medium / low
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate(self) -> list[str]:
        errors = []
        if not self.session_id:
            errors.append("session_id is required")
        if self.confidence not in ("high", "medium", "low"):
            errors.append(f"invalid confidence: {self.confidence}")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "consistency_score": round(self.consistency_score, 1),
            "trend": self.trend,
            "focus_area": self.focus_area,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


@dataclass
class EventPayload:
    session_id: str
    event_type: str     # pit_stop / alert / strategy_update
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors = []
        if not self.session_id:
            errors.append("session_id is required")
        if not self.event_type:
            errors.append("event_type is required")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }


@dataclass
class SyncEnvelope:
    """Wraps any payload with metadata for idempotent delivery."""
    envelope_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    payload_type: str = ""     # session / lap / coaching / event
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    attempt_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "payload_type": self.payload_type,
            "payload": self.payload,
            "created_at": self.created_at,
            "attempt_count": self.attempt_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SyncEnvelope:
        return cls(
            envelope_id=d.get("envelope_id", str(uuid.uuid4())),
            payload_type=d.get("payload_type", ""),
            payload=d.get("payload", {}),
            created_at=d.get("created_at", ""),
            attempt_count=d.get("attempt_count", 0),
        )
