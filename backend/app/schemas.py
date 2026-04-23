"""Pydantic schemas — request/response shapes.

Mirrors desktop sync/schema.py so client-side and server-side validation
reject the same payloads. Any rule here must have a matching rule in the
desktop's LapPayload.validate() etc.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


SessionMode = Literal["sprint", "endurance", "coaching", "data"]
Confidence = Literal["high", "medium", "low"]

# Session IDs are UUIDs / ULIDs / short hex tokens in practice. Constrain
# the charset everywhere so a malformed client can't inject control chars
# (NUL, CR/LF) or oversized strings that break log pipelines or FK lookups.
SessionId = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]{1,64}$")]


# ---------------------------------------------------------------------------
# Auth (webapp)
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str


# ---------------------------------------------------------------------------
# Ingest — desktop -> backend
# ---------------------------------------------------------------------------

class SessionIn(BaseModel):
    session_id: SessionId
    sim: str = Field(min_length=1)
    track: str = Field(min_length=1)
    car: str = Field(min_length=1)
    mode: SessionMode
    start_time: datetime
    end_time: str = ""  # desktop sends ISO string; coerced to datetime only on /sessions-end
    sample_count: int = 0
    driver_name: str = ""


class SessionEndIn(BaseModel):
    session_id: SessionId
    sim: str
    track: str
    car: str
    mode: SessionMode
    start_time: datetime
    end_time: datetime   # required here, unlike /sessions-start
    sample_count: int = 0
    driver_name: str = ""


class LapIn(BaseModel):
    session_id: SessionId
    lap_number: int = Field(ge=0)
    lap_time_s: float = Field(gt=0)
    valid: bool = True
    fuel_used_l: float = 0.0
    sector_times_s: list[float] = Field(default_factory=list)
    consistency_pct: float | None = None
    std_dev_s: float | None = None


class LapsBatchIn(BaseModel):
    laps: list[LapIn] = Field(min_length=1, max_length=200)

    @field_validator("laps")
    @classmethod
    def _single_session(cls, v: list[LapIn]) -> list[LapIn]:
        if len({l.session_id for l in v}) != 1:
            raise ValueError("all laps in a batch must share the same session_id")
        return v


class CoachingIn(BaseModel):
    session_id: SessionId
    consistency_score: float
    trend: str = Field(min_length=1)
    focus_area: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    confidence: Confidence
    timestamp: datetime


class CoachingBatchIn(BaseModel):
    coaching: list[CoachingIn] = Field(min_length=1, max_length=200)

    @field_validator("coaching")
    @classmethod
    def _single_session(cls, v: list[CoachingIn]) -> list[CoachingIn]:
        if len({c.session_id for c in v}) != 1:
            raise ValueError("all coaching items must share the same session_id")
        return v


class EventIn(BaseModel):
    session_id: SessionId
    event_type: str = Field(min_length=1, max_length=64)
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class EventsBatchIn(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=200)

    @field_validator("events")
    @classmethod
    def _single_session(cls, v: list[EventIn]) -> list[EventIn]:
        if len({e.session_id for e in v}) != 1:
            raise ValueError("all events must share the same session_id")
        return v


# ---------------------------------------------------------------------------
# Envelope response
# ---------------------------------------------------------------------------

class AcceptResponse(BaseModel):
    ok: Literal[True] = True
    envelope_id: uuid.UUID
    already_seen: bool = False


# ---------------------------------------------------------------------------
# Read — backend -> webapp
# ---------------------------------------------------------------------------

class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    session_id: str
    sim: str
    track: str
    car: str
    mode: SessionMode
    driver_name: str
    start_time: datetime
    end_time: datetime | None
    sample_count: int
    lap_count: int = 0  # joined in the router
    # Canonical fields (v2 — may be null if unresolved)
    canonical_car_id: uuid.UUID | None = None
    canonical_car_name: str | None = None
    car_class: str | None = None
    canonical_track_id: uuid.UUID | None = None
    canonical_track_name: str | None = None
    track_layout: str | None = None


class LapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    lap_number: int
    lap_time_s: float
    valid: bool
    fuel_used_l: float
    sector_times_s: list[float]
    consistency_pct: float | None
    std_dev_s: float | None


class CoachingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    consistency_score: float
    trend: str
    focus_area: str
    recommendation: str
    confidence: Confidence
    emitted_at: datetime


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_type: str
    occurred_at: datetime
    payload: dict[str, Any]


class SessionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    session_id: str
    sim: str
    track: str
    car: str
    mode: SessionMode
    driver_name: str
    start_time: datetime
    end_time: datetime | None
    sample_count: int
    source: str
    schema_version: int
    device_token: str
    envelope_count: int
    # Canonical fields (v2)
    canonical_car_id: uuid.UUID | None = None
    canonical_car_name: str | None = None
    car_class: str | None = None
    canonical_track_id: uuid.UUID | None = None
    canonical_track_name: str | None = None
    track_layout: str | None = None
    bundle_hash: str | None = None
    analysis_json: dict[str, Any] | None = None
    laps: list[LapOut]
    coaching: list[CoachingOut]
    events: list[EventOut]
