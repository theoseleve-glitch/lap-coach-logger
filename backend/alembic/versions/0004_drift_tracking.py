"""Drift + unresolved tracking tables.

Revision ID: 0004_drift_tracking
Revises: 0003_sessions_extensions
Create Date: 2026-04-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_drift_tracking"
down_revision = "0003_sessions_extensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # canonical_drifts — one row per field per session where desktop disagrees with backend
    op.create_table(
        "canonical_drifts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Text,
                  sa.ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field", sa.Text, nullable=False),
        sa.Column("submitted_value", sa.Text, nullable=True),
        sa.Column("backend_value", sa.Text, nullable=True),
        sa.Column("sim_id", sa.Text, nullable=False),
        sa.Column("raw_value", sa.Text, nullable=False),
        sa.Column("desktop_lut_version", sa.Text, nullable=True),
        sa.Column("backend_lut_version", sa.Text, nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # unresolved_canonicals — aggregated unknowns for curator triage
    op.create_table(
        "unresolved_canonicals",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("sim_id", sa.Text, nullable=False),
        sa.Column("raw_car", sa.Text, nullable=True),
        sa.Column("raw_track", sa.Text, nullable=True),
        sa.Column("raw_track_layout", sa.Text, nullable=True),
        sa.Column("occurrence_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("sim_id", "raw_car", "raw_track", "raw_track_layout", name="unresolved_unique"),
    )


def downgrade() -> None:
    op.drop_table("unresolved_canonicals")
    op.drop_table("canonical_drifts")
