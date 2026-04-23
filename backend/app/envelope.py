"""Envelope helpers — idempotency key parsing, per-row UUIDv5 derivation, audit insert."""

from __future__ import annotations

import uuid

from fastapi import Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import models


# RFC 4122 URL namespace — stable seed for UUIDv5.
APP_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def idempotency_key(idempotency_key: str = Header(..., alias="Idempotency-Key")) -> uuid.UUID:
    """FastAPI dependency — parses the Idempotency-Key header as a UUID.

    Rejects missing or malformed keys with a 400 that matches the
    desktop's expected error shape.
    """
    try:
        return uuid.UUID(idempotency_key)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "code": "missing_envelope_id", "message": "Idempotency-Key must be a UUID"},
        )


def derive_envelope_id(batch_envelope: uuid.UUID, key: str | int) -> uuid.UUID:
    """UUIDv5 from (batch_envelope, per-row key).

    Deterministic — same inputs always produce the same UUID — which is
    what makes per-row idempotency work on partial-batch replay.
    """
    # uuid.uuid5 uses SHA-1 under the hood and produces a compliant UUIDv5.
    return uuid.uuid5(batch_envelope, f"{batch_envelope}:{key}")


async def envelope_already_seen(db: AsyncSession, envelope_id: uuid.UUID) -> bool:
    """True iff sync_envelopes contains a row with this envelope_id."""
    stmt = select(models.SyncEnvelope.envelope_id).where(
        models.SyncEnvelope.envelope_id == envelope_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def record_envelope(
    db: AsyncSession,
    *,
    envelope_id: uuid.UUID,
    user_id: uuid.UUID,
    device_token: str,
    payload_type: str,
    session_id: str | None,
) -> None:
    """Insert into sync_envelopes. ON CONFLICT DO NOTHING on the PK so a
    concurrent replay (two desktop retries arriving at once) resolves cleanly
    without throwing IntegrityError — the router can't distinguish a genuine
    race loser from e.g. an FK violation without this."""
    stmt = pg_insert(models.SyncEnvelope).values(
        envelope_id=envelope_id,
        user_id=user_id,
        device_token=device_token,
        payload_type=payload_type,
        session_id=session_id,
    ).on_conflict_do_nothing(index_elements=["envelope_id"])
    await db.execute(stmt)
