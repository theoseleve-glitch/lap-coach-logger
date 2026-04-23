"""Authentication — two paths, one user table.

- **Device token** (desktop): Authorization: Bearer <token> → devices.user_id
- **Webapp session**: HttpOnly JWT cookie signed with settings.secret_key

Both paths resolve to a User row loaded via SQLAlchemy. Endpoints pick
the dependency they accept — ingest endpoints use `current_device`, read
endpoints use `current_user`. There's no cross-wiring.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.config import Settings, get_settings
from app.database import get_db


_hasher = PasswordHasher()


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(raw: str) -> str:
    return _hasher.hash(raw)


def verify_password(stored_hash: str, raw: str) -> bool:
    try:
        _hasher.verify(stored_hash, raw)
        return True
    except VerifyMismatchError:
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT session for webapp
# ---------------------------------------------------------------------------

def issue_session_token(user_id: uuid.UUID, settings: Settings) -> str:
    """Sign a JWT naming the user for ``session_ttl_hours``."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.session_ttl_hours)).timestamp()),
        "typ": "session",
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_session_token(token: str, settings: Settings) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "session":
        return None
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DeviceIdentity:
    user: models.User
    device: models.Device


async def current_device(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> DeviceIdentity:
    """Require a valid device token. Returns the joined user + device."""
    token = _parse_bearer(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ok": False, "code": "auth_failed", "message": "invalid or missing device token"},
        )
    stmt = (
        select(models.Device, models.User)
        .join(models.User, models.User.id == models.Device.user_id)
        .where(models.Device.device_token == token)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ok": False, "code": "auth_failed", "message": "unknown device token"},
        )
    device, user = row
    # Touch last_seen_at opportunistically; don't block the request on a failure.
    device.last_seen_at = datetime.now(timezone.utc)
    await db.flush()
    return DeviceIdentity(user=user, device=device)


def _parse_bearer(header: str | None) -> str | None:
    if not header or not header.lower().startswith("bearer "):
        return None
    token = header[7:].strip()
    return token or None


async def current_user(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    lc_session: str | None = Cookie(default=None),
) -> models.User:
    """Require a valid session cookie; return the User."""
    if not lc_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ok": False, "code": "not_authenticated"},
        )
    user_id = decode_session_token(lc_session, settings)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ok": False, "code": "invalid_session"},
        )
    user = await db.get(models.User, user_id)
    if not user:
        # Session signed for a user that no longer exists.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ok": False, "code": "user_gone"},
        )
    return user
