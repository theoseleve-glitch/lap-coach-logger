"""One-shot CLI: create a user + device token.

Usage:

    DATABASE_URL=postgresql+asyncpg://... \
    python -m scripts.create_user alice@example.com --label "Alice laptop"

Prints the device token on success. Password is read from stdin
(hidden). This is the only way to add a user in RC1 — there is no
self-service registration.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import secrets
import sys

from sqlalchemy import select

from app import models
from app.auth import hash_password
from app.database import configure_engine, get_db


async def _create(email: str, password: str, label: str | None) -> tuple[str, str]:
    # Walk the async generator without FastAPI's dependency machinery.
    async for db in get_db():
        existing = (await db.execute(
            select(models.User).where(models.User.email == email.lower())
        )).scalar_one_or_none()
        if existing:
            raise SystemExit(f"user {email!r} already exists")

        user = models.User(
            email=email.lower(),
            password_hash=hash_password(password),
            display_name=email.split("@")[0],
        )
        db.add(user)
        await db.flush()

        device_token = secrets.token_hex(32)  # 64 hex chars
        device = models.Device(
            device_token=device_token,
            user_id=user.id,
            label=label,
        )
        db.add(device)
        await db.commit()
        return str(user.id), device_token
    raise SystemExit("could not open database session")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="login email")
    parser.add_argument("--label", default=None, help="optional device label")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL env var is required", file=sys.stderr)
        return 2
    configure_engine(url)

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm : ")
    if password != confirm:
        print("passwords do not match", file=sys.stderr)
        return 2
    if len(password) < 8:
        print("password must be at least 8 chars", file=sys.stderr)
        return 2

    user_id, token = asyncio.run(_create(args.email, password, args.label))
    print(f"user_id:      {user_id}")
    print(f"device_token: {token}")
    print()
    print("Put the device token into the desktop settings. The user_id is")
    print("informational — the webapp identifies by email/password.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
