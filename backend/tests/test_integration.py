"""Integration tests against a live Postgres.

Covers the scenarios from the Connected v1 spec:
  - auth failure (no token / bad token)
  - invalid payload rejection
  - duplicate replay returns already_seen=True
  - missing session → 409
  - cross-user isolation
  - webapp login + /sessions visibility
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from tests.conftest import make_device, make_user, needs_db


pytestmark = needs_db  # skip whole module if no DB


def _session_payload(session_id: str | None = None) -> dict:
    return {
        "session_id": session_id or str(uuid.uuid4()),
        "sim": "iRacing", "track": "Monza", "car": "GT3",
        "mode": "sprint",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "end_time": "",
        "sample_count": 0,
        "driver_name": "Daisy",
    }


class TestAuth:
    async def test_missing_token_is_401(self, client: AsyncClient) -> None:
        r = await client.post(
            "/sessions-start",
            json=_session_payload(),
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "auth_failed"

    async def test_unknown_token_is_401(self, client: AsyncClient) -> None:
        r = await client.post(
            "/sessions-start",
            json=_session_payload(),
            headers={
                "Idempotency-Key": str(uuid.uuid4()),
                "Authorization": "Bearer unknown-token",
            },
        )
        assert r.status_code == 401


class TestSessionsStart:
    async def test_accepts_valid(self, client: AsyncClient, db) -> None:
        user = await make_user(db, "alice@example.com")
        device = await make_device(db, user)
        envelope = uuid.uuid4()

        r = await client.post(
            "/sessions-start",
            json=_session_payload(),
            headers={
                "Idempotency-Key": str(envelope),
                "Authorization": f"Bearer {device.device_token}",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["already_seen"] is False
        assert body["envelope_id"] == str(envelope)

    async def test_replay_returns_already_seen(self, client: AsyncClient, db) -> None:
        user = await make_user(db, "alice@example.com")
        device = await make_device(db, user)
        envelope = uuid.uuid4()
        payload = _session_payload()
        hdrs = {
            "Idempotency-Key": str(envelope),
            "Authorization": f"Bearer {device.device_token}",
        }

        r1 = await client.post("/sessions-start", json=payload, headers=hdrs)
        r2 = await client.post("/sessions-start", json=payload, headers=hdrs)

        assert r1.status_code == 200 and r1.json()["already_seen"] is False
        assert r2.status_code == 200 and r2.json()["already_seen"] is True

    async def test_invalid_payload_is_400(self, client: AsyncClient, db) -> None:
        user = await make_user(db, "alice@example.com")
        device = await make_device(db, user)
        bad = _session_payload()
        bad["mode"] = "nonsense"

        r = await client.post(
            "/sessions-start", json=bad,
            headers={
                "Idempotency-Key": str(uuid.uuid4()),
                "Authorization": f"Bearer {device.device_token}",
            },
        )
        assert r.status_code == 400
        body = r.json()
        assert body["code"] == "invalid_payload"
        assert body["field"] == "mode"

    async def test_missing_idempotency_key_is_400(self, client: AsyncClient, db) -> None:
        user = await make_user(db, "alice@example.com")
        device = await make_device(db, user)
        r = await client.post(
            "/sessions-start", json=_session_payload(),
            headers={"Authorization": f"Bearer {device.device_token}"},
        )
        assert r.status_code == 400


class TestMissingSession:
    async def test_laps_without_session_is_409(self, client: AsyncClient, db) -> None:
        user = await make_user(db, "alice@example.com")
        device = await make_device(db, user)
        r = await client.post(
            "/laps-batch",
            json={"laps": [{
                "session_id": "never-exists",
                "lap_number": 1, "lap_time_s": 92.3, "valid": True,
                "fuel_used_l": 2.1, "sector_times_s": [30.0, 30.0, 32.3],
            }]},
            headers={
                "Idempotency-Key": str(uuid.uuid4()),
                "Authorization": f"Bearer {device.device_token}",
            },
        )
        assert r.status_code == 409
        assert r.json()["code"] == "missing_session"


class TestIsolation:
    async def test_user_b_cannot_see_user_a_sessions(
        self, client: AsyncClient, db,
    ) -> None:
        # Create A + session on A's device.
        alice = await make_user(db, "alice@example.com")
        alice_device = await make_device(db, alice)
        await client.post(
            "/sessions-start", json=_session_payload(session_id="alice-session"),
            headers={
                "Idempotency-Key": str(uuid.uuid4()),
                "Authorization": f"Bearer {alice_device.device_token}",
            },
        )

        # Create B and log in.
        await make_user(db, "bob@example.com", password="hunter2hunter2")
        login = await client.post(
            "/auth/login",
            json={"email": "bob@example.com", "password": "hunter2hunter2"},
        )
        assert login.status_code == 200
        # httpx.AsyncClient carries the cookie forward.
        sessions = await client.get("/sessions")
        assert sessions.status_code == 200
        assert sessions.json() == []

        # B cannot probe by ID either.
        detail = await client.get("/sessions/alice-session")
        assert detail.status_code == 404


class TestWebappFlow:
    async def test_login_sets_cookie_and_me_returns_user(
        self, client: AsyncClient, db,
    ) -> None:
        await make_user(db, "alice@example.com", password="hunter2hunter2")
        r = await client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "hunter2hunter2"},
        )
        assert r.status_code == 200
        assert "lc_session" in client.cookies

        me = await client.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "alice@example.com"

    async def test_wrong_password_is_401(self, client: AsyncClient, db) -> None:
        await make_user(db, "alice@example.com", password="hunter2hunter2")
        r = await client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "nope"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "invalid_credentials"

    async def test_me_without_cookie_is_401(self, client: AsyncClient) -> None:
        r = await client.get("/auth/me")
        assert r.status_code == 401

    async def test_full_round_trip_session_visible_in_history(
        self, client: AsyncClient, db,
    ) -> None:
        user = await make_user(db, "alice@example.com", password="hunter2hunter2")
        device = await make_device(db, user)

        # Ingest a session via device token.
        payload = _session_payload()
        await client.post(
            "/sessions-start", json=payload,
            headers={
                "Idempotency-Key": str(uuid.uuid4()),
                "Authorization": f"Bearer {device.device_token}",
            },
        )

        # Log in and read history.
        await client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "hunter2hunter2"},
        )
        r = await client.get("/sessions")
        assert r.status_code == 200
        history = r.json()
        assert len(history) == 1
        assert history[0]["session_id"] == payload["session_id"]
