"""SQLAlchemy ORM models — one class per Postgres table.

Shapes mirror the desktop sync/schema.py payloads so round-tripping is
zero-surprise. No business logic here; helpers live in routers and utils.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Double,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# users — webapp-side identity
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)


# ---------------------------------------------------------------------------
# devices — desktop-side identity
# ---------------------------------------------------------------------------

class Device(Base):
    __tablename__ = "devices"

    device_token: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# sessions — one per completed recording
# ---------------------------------------------------------------------------

class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_token: Mapped[str] = mapped_column(Text, ForeignKey("devices.device_token", ondelete="CASCADE"), nullable=False)
    envelope_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), unique=True, nullable=False)
    sim: Mapped[str] = mapped_column(Text, nullable=False)
    track: Mapped[str] = mapped_column(Text, nullable=False)
    car: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    driver_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    start_time: Mapped[datetime] = mapped_column(nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="desktop")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    # -- v2 extensions (Phase 1 — canonical resolution) -------------------------
    canonical_car_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cars.canonical_id"), nullable=True,
    )
    canonical_track_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tracks.canonical_id"), nullable=True,
    )
    car_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    track_layout: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    telemetry_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_telemetry_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    bundle_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_drift_flags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}",
    )
    last_canonicalized_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        CheckConstraint("mode IN ('sprint','endurance','coaching','data')", name="sessions_mode_ck"),
        Index("sessions_user_start_idx", "user_id", "start_time"),
        Index("sessions_user_mode_idx", "user_id", "mode"),
    )


# ---------------------------------------------------------------------------
# laps
# ---------------------------------------------------------------------------

class Lap(Base):
    __tablename__ = "laps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    envelope_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), unique=True, nullable=False)
    lap_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lap_time_s: Mapped[float] = mapped_column(Double, nullable=False)
    valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fuel_used_l: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    sector_times_s: Mapped[list[float]] = mapped_column(ARRAY(Double), nullable=False, default=list)
    consistency_pct: Mapped[float | None] = mapped_column(Double, nullable=True)
    std_dev_s: Mapped[float | None] = mapped_column(Double, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("lap_time_s > 0", name="laps_positive_time_ck"),
        UniqueConstraint("session_id", "lap_number", name="laps_session_number_uq"),
        Index("laps_session_idx", "session_id", "lap_number"),
        Index("laps_user_created_idx", "user_id", "created_at"),
    )


# ---------------------------------------------------------------------------
# coaching_outputs
# ---------------------------------------------------------------------------

class CoachingOutput(Base):
    __tablename__ = "coaching_outputs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    envelope_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), unique=True, nullable=False)
    consistency_score: Mapped[float] = mapped_column(Double, nullable=False)
    trend: Mapped[str] = mapped_column(Text, nullable=False)
    focus_area: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(Text, nullable=False)
    emitted_at: Mapped[datetime] = mapped_column(nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("confidence IN ('high','medium','low')", name="coaching_confidence_ck"),
        Index("coaching_session_idx", "session_id", "emitted_at"),
    )


# ---------------------------------------------------------------------------
# session_events
# ---------------------------------------------------------------------------

class SessionEvent(Base):
    __tablename__ = "session_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    envelope_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("events_session_occurred_idx", "session_id", "occurred_at"),
    )


# ---------------------------------------------------------------------------
# sync_envelopes — audit log
# ---------------------------------------------------------------------------

class SyncEnvelope(Base):
    __tablename__ = "sync_envelopes"

    envelope_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_token: Mapped[str] = mapped_column(Text, ForeignKey("devices.device_token", ondelete="CASCADE"), nullable=False)
    payload_type: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("sync_envelopes_user_received_idx", "user_id", "received_at"),
    )


# ---------------------------------------------------------------------------
# sync_failures — server-side audit
# ---------------------------------------------------------------------------

class SyncFailure(Base):
    __tablename__ = "sync_failures"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    envelope_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    payload_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    request_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("sync_failures_user_occurred_idx", "user_id", "occurred_at"),
    )


# =========================================================================
# Canonical registry (Phase 1 — Connected v1)
# =========================================================================


class Sim(Base):
    """Static reference table. 4 rows seeded, rarely modified."""
    __tablename__ = "sims"

    sim_id: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class Car(Base):
    """Canonical car — one row per real-world car regardless of sim."""
    __tablename__ = "cars"

    canonical_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    car_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class CarAlias(Base):
    """Maps (sim_id, raw_id) → canonical_id. One car may have multiple aliases."""
    __tablename__ = "car_aliases"

    sim_id: Mapped[str] = mapped_column(Text, ForeignKey("sims.sim_id"), primary_key=True)
    raw_id: Mapped[str] = mapped_column(Text, primary_key=True)
    canonical_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cars.canonical_id"), nullable=False, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class Track(Base):
    """Canonical track — one row per real-world circuit."""
    __tablename__ = "tracks"

    canonical_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    length_m: Mapped[float | None] = mapped_column(Double, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class TrackAlias(Base):
    """Maps (sim_id, raw_id, raw_layout) → (canonical_id, canonical_layout)."""
    __tablename__ = "track_aliases"

    sim_id: Mapped[str] = mapped_column(Text, ForeignKey("sims.sim_id"), primary_key=True)
    raw_id: Mapped[str] = mapped_column(Text, primary_key=True)
    raw_layout: Mapped[str] = mapped_column(Text, primary_key=True, default="")
    canonical_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tracks.canonical_id"), nullable=False, index=True,
    )
    canonical_layout: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


# =========================================================================
# Drift + unresolved tracking (Phase 1)
# =========================================================================


class CanonicalDrift(Base):
    """Records cases where desktop's canonical_id disagrees with backend's."""
    __tablename__ = "canonical_drifts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    field: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    backend_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    sim_id: Mapped[str] = mapped_column(Text, nullable=False)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    desktop_lut_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    backend_lut_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class UnresolvedCanonical(Base):
    """Aggregates unresolvable (sim, raw_car/track) pairs for curator triage."""
    __tablename__ = "unresolved_canonicals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sim_id: Mapped[str] = mapped_column(Text, nullable=False)
    raw_car: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_track: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_track_layout: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("sim_id", "raw_car", "raw_track", "raw_track_layout", name="unresolved_unique"),
    )
