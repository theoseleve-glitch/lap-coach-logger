"""Canonical registry — sims, cars, car_aliases, tracks, track_aliases.

Revision ID: 0002_canonical_registry
Revises: 0001_connected_v1
Create Date: 2026-04-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_canonical_registry"
down_revision = "0001_connected_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # sims — static, seeded with 4 rows
    op.create_table(
        "sims",
        sa.Column("sim_id", sa.Text, primary_key=True),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("is_supported", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Seed the 4 supported sims
    sims_table = sa.table(
        "sims",
        sa.column("sim_id", sa.Text),
        sa.column("display_name", sa.Text),
        sa.column("is_supported", sa.Boolean),
    )
    op.bulk_insert(sims_table, [
        {"sim_id": "iracing",        "display_name": "iRacing",                    "is_supported": True},
        {"sim_id": "acc",            "display_name": "Assetto Corsa Competizione", "is_supported": True},
        {"sim_id": "assetto_corsa",  "display_name": "Assetto Corsa",             "is_supported": True},
        {"sim_id": "lmu",            "display_name": "Le Mans Ultimate",           "is_supported": True},
    ])

    # cars — canonical car registry
    op.create_table(
        "cars",
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_name", sa.Text, nullable=False),
        sa.Column("car_class", sa.Text, nullable=True),
        sa.Column("manufacturer", sa.Text, nullable=True),
        sa.Column("model", sa.Text, nullable=True),
        sa.Column("year", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # car_aliases
    op.create_table(
        "car_aliases",
        sa.Column("sim_id", sa.Text, sa.ForeignKey("sims.sim_id"), primary_key=True),
        sa.Column("raw_id", sa.Text, primary_key=True),
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cars.canonical_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("car_aliases_canonical_idx", "car_aliases", ["canonical_id"])

    # tracks — canonical track registry
    op.create_table(
        "tracks",
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_name", sa.Text, nullable=False),
        sa.Column("country", sa.Text, nullable=True),
        sa.Column("length_m", sa.Double, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # track_aliases
    op.create_table(
        "track_aliases",
        sa.Column("sim_id", sa.Text, sa.ForeignKey("sims.sim_id"), primary_key=True),
        sa.Column("raw_id", sa.Text, primary_key=True),
        sa.Column("raw_layout", sa.Text, primary_key=True, server_default=""),
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tracks.canonical_id"), nullable=False),
        sa.Column("canonical_layout", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("track_aliases_canonical_idx", "track_aliases", ["canonical_id"])


def downgrade() -> None:
    op.drop_table("track_aliases")
    op.drop_table("car_aliases")
    op.drop_table("tracks")
    op.drop_table("cars")
    op.drop_table("sims")
