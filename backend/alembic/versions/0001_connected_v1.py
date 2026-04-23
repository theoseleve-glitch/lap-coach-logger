"""Connected v1 — all 7 tables.

Revision ID: 0001_connected_v1
Revises:
Create Date: 2026-04-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0001_connected_v1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("users_email_idx", "users", ["email"])

    # devices
    op.create_table(
        "devices",
        sa.Column("device_token", sa.Text, primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("devices_user_id_idx", "devices", ["user_id"])

    # sessions
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.Text, primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_token", sa.Text,
                  sa.ForeignKey("devices.device_token", ondelete="CASCADE"), nullable=False),
        sa.Column("envelope_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("sim", sa.Text, nullable=False),
        sa.Column("track", sa.Text, nullable=False),
        sa.Column("car", sa.Text, nullable=False),
        sa.Column("mode", sa.Text, nullable=False),
        sa.Column("driver_name", sa.Text, nullable=False, server_default=""),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sample_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("source", sa.Text, nullable=False, server_default="desktop"),
        sa.Column("schema_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("mode IN ('sprint','endurance','coaching','data')", name="sessions_mode_ck"),
    )
    op.create_index("sessions_user_start_idx", "sessions", ["user_id", "start_time"])
    op.create_index("sessions_user_mode_idx", "sessions", ["user_id", "mode"])

    # laps
    op.create_table(
        "laps",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Text,
                  sa.ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("envelope_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("lap_number", sa.Integer, nullable=False),
        sa.Column("lap_time_s", sa.Double, nullable=False),
        sa.Column("valid", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("fuel_used_l", sa.Double, nullable=False, server_default="0"),
        sa.Column("sector_times_s", postgresql.ARRAY(sa.Double), nullable=False, server_default="{}"),
        sa.Column("consistency_pct", sa.Double, nullable=True),
        sa.Column("std_dev_s", sa.Double, nullable=True),
        sa.Column("schema_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("lap_time_s > 0", name="laps_positive_time_ck"),
        sa.UniqueConstraint("session_id", "lap_number", name="laps_session_number_uq"),
    )
    op.create_index("laps_session_idx", "laps", ["session_id", "lap_number"])
    op.create_index("laps_user_created_idx", "laps", ["user_id", "created_at"])

    # coaching_outputs
    op.create_table(
        "coaching_outputs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Text,
                  sa.ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("envelope_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("consistency_score", sa.Double, nullable=False),
        sa.Column("trend", sa.Text, nullable=False),
        sa.Column("focus_area", sa.Text, nullable=False),
        sa.Column("recommendation", sa.Text, nullable=False),
        sa.Column("confidence", sa.Text, nullable=False),
        sa.Column("emitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("confidence IN ('high','medium','low')", name="coaching_confidence_ck"),
    )
    op.create_index("coaching_session_idx", "coaching_outputs", ["session_id", "emitted_at"])

    # session_events
    op.create_table(
        "session_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Text,
                  sa.ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("envelope_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("schema_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("events_session_occurred_idx", "session_events", ["session_id", "occurred_at"])

    # sync_envelopes
    op.create_table(
        "sync_envelopes",
        sa.Column("envelope_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_token", sa.Text,
                  sa.ForeignKey("devices.device_token", ondelete="CASCADE"), nullable=False),
        sa.Column("payload_type", sa.Text, nullable=False),
        sa.Column("session_id", sa.Text, nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("sync_envelopes_user_received_idx", "sync_envelopes", ["user_id", "received_at"])

    # sync_failures
    op.create_table(
        "sync_failures",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("envelope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload_type", sa.Text, nullable=True),
        sa.Column("error_code", sa.Text, nullable=False),
        sa.Column("error_message", sa.Text, nullable=False),
        sa.Column("request_body", postgresql.JSONB, nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("sync_failures_user_occurred_idx", "sync_failures", ["user_id", "occurred_at"])


def downgrade() -> None:
    for table in (
        "sync_failures", "sync_envelopes", "session_events",
        "coaching_outputs", "laps", "sessions", "devices", "users",
    ):
        op.drop_table(table)
