"""Pure-function unit tests — no DB needed, always run."""

from __future__ import annotations

import uuid

from app.auth import (
    decode_session_token,
    hash_password,
    issue_session_token,
    verify_password,
)
from app.config import Settings
from app.envelope import APP_NAMESPACE, derive_envelope_id


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

class TestPasswords:
    def test_round_trip(self) -> None:
        h = hash_password("hunter2hunter2")
        assert verify_password(h, "hunter2hunter2") is True

    def test_rejects_wrong_password(self) -> None:
        h = hash_password("hunter2hunter2")
        assert verify_password(h, "hunter3") is False

    def test_rejects_garbage_hash(self) -> None:
        assert verify_password("not-a-hash", "whatever") is False


# ---------------------------------------------------------------------------
# JWT session tokens
# ---------------------------------------------------------------------------

def _settings() -> Settings:
    return Settings(database_url="x", secret_key="0" * 64)  # type: ignore[call-arg]


class TestSessionToken:
    def test_round_trip(self) -> None:
        s = _settings()
        user_id = uuid.uuid4()
        token = issue_session_token(user_id, s)
        assert decode_session_token(token, s) == user_id

    def test_rejects_garbage(self) -> None:
        assert decode_session_token("not.a.jwt", _settings()) is None

    def test_rejects_wrong_signature(self) -> None:
        s1 = _settings()
        s2 = Settings(database_url="x", secret_key="1" * 64)  # type: ignore[call-arg]
        token = issue_session_token(uuid.uuid4(), s1)
        assert decode_session_token(token, s2) is None


# ---------------------------------------------------------------------------
# Envelope derivation
# ---------------------------------------------------------------------------

class TestDeriveEnvelope:
    def test_is_uuid5(self) -> None:
        batch = uuid.uuid4()
        child = derive_envelope_id(batch, 0)
        assert child.version == 5

    def test_deterministic(self) -> None:
        batch = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        a = derive_envelope_id(batch, 3)
        b = derive_envelope_id(batch, 3)
        assert a == b

    def test_different_keys_give_different_ids(self) -> None:
        batch = uuid.uuid4()
        ids = {derive_envelope_id(batch, i) for i in range(100)}
        assert len(ids) == 100

    def test_different_batches_give_different_ids(self) -> None:
        a = derive_envelope_id(uuid.uuid4(), 0)
        b = derive_envelope_id(uuid.uuid4(), 0)
        assert a != b

    def test_namespace_is_app_namespace(self) -> None:
        # Sanity check that we haven't accidentally swapped the namespace.
        assert APP_NAMESPACE == uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
