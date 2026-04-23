"""Sessions table v2 extensions — canonical IDs, analysis, bundle metadata.

Revision ID: 0003_sessions_extensions
Revises: 0002_canonical_registry
Create Date: 2026-04-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_sessions_extensions"
down_revision = "0002_canonical_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column(
        "canonical_car_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("cars.canonical_id"), nullable=True,
    ))
    op.add_column("sessions", sa.Column(
        "canonical_track_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("tracks.canonical_id"), nullable=True,
    ))
    op.add_column("sessions", sa.Column("car_class", sa.Text, nullable=True))
    op.add_column("sessions", sa.Column("track_layout", sa.Text, nullable=True))
    op.add_column("sessions", sa.Column("analysis_json", postgresql.JSONB, nullable=True))
    op.add_column("sessions", sa.Column("telemetry_path", sa.Text, nullable=True))
    op.add_column("sessions", sa.Column("raw_telemetry_path", sa.Text, nullable=True))
    op.add_column("sessions", sa.Column("bundle_hash", sa.Text, nullable=True))
    op.add_column("sessions", sa.Column(
        "canonical_drift_flags", postgresql.ARRAY(sa.Text),
        nullable=False, server_default="{}",
    ))
    op.add_column("sessions", sa.Column(
        "last_canonicalized_at", sa.DateTime(timezone=True), nullable=True,
    ))


def downgrade() -> None:
    for col in (
        "last_canonicalized_at", "canonical_drift_flags", "bundle_hash",
        "raw_telemetry_path", "telemetry_path", "analysis_json",
        "track_layout", "car_class", "canonical_track_id", "canonical_car_id",
    ):
        op.drop_column("sessions", col)
