"""T050: OS keychain-backed token storage.

ADR-011 mandates that desktop stores Clerk refresh tokens in the
OS keychain (Windows Credential Manager / macOS Keychain / Linux
Secret Service). The ``TokenStore`` wraps the ``keyring`` library
and exposes a tiny account-keyed API so the rest of the app never
imports ``keyring`` directly — that lets us inject a fake backend
in tests, and lets the auth wiring depend on a stable interface
even if we ever swap to a different secret backend.

Tests use an in-memory fake that mimics ``keyring``'s module-level
``set_password`` / ``get_password`` / ``delete_password`` surface
plus ``errors.PasswordDeleteError``. This keeps the suite hermetic
on every OS — we never touch the real Credential Manager.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


class _PasswordDeleteError(Exception):
    """Mimics ``keyring.errors.PasswordDeleteError``."""


class _FakeKeyringModule:
    """In-memory keyring backend exposing the module-level API surface."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}
        self.errors = SimpleNamespace(PasswordDeleteError=_PasswordDeleteError)

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self._store:
            raise _PasswordDeleteError(f"no entry for ({service}, {username})")
        del self._store[(service, username)]


@pytest.fixture
def fake_keyring() -> _FakeKeyringModule:
    return _FakeKeyringModule()


def test_save_then_load_roundtrips_the_refresh_token(
    fake_keyring: _FakeKeyringModule,
) -> None:
    from lap_coach_logger.infra.token_store import TokenStore

    store = TokenStore(keyring_module=fake_keyring)

    store.save_refresh_token(account="theos.eleve@gmail.com", refresh_token="rt-abc")

    assert store.load_refresh_token("theos.eleve@gmail.com") == "rt-abc"


def test_load_returns_none_when_nothing_stored(
    fake_keyring: _FakeKeyringModule,
) -> None:
    from lap_coach_logger.infra.token_store import TokenStore

    store = TokenStore(keyring_module=fake_keyring)

    assert store.load_refresh_token("theos.eleve@gmail.com") is None


def test_clear_removes_the_stored_token(
    fake_keyring: _FakeKeyringModule,
) -> None:
    from lap_coach_logger.infra.token_store import TokenStore

    store = TokenStore(keyring_module=fake_keyring)
    store.save_refresh_token(account="x@y.z", refresh_token="rt-1")

    store.clear_refresh_token("x@y.z")

    assert store.load_refresh_token("x@y.z") is None


def test_clear_is_idempotent_when_nothing_was_stored(
    fake_keyring: _FakeKeyringModule,
) -> None:
    """Callers shouldn't have to track existence to call clear safely."""
    from lap_coach_logger.infra.token_store import TokenStore

    store = TokenStore(keyring_module=fake_keyring)

    # Must not raise.
    store.clear_refresh_token("never-saved@example.com")


def test_multiple_accounts_are_kept_separate(
    fake_keyring: _FakeKeyringModule,
) -> None:
    from lap_coach_logger.infra.token_store import TokenStore

    store = TokenStore(keyring_module=fake_keyring)
    store.save_refresh_token(account="alice@example.com", refresh_token="rt-alice")
    store.save_refresh_token(account="bob@example.com", refresh_token="rt-bob")

    assert store.load_refresh_token("alice@example.com") == "rt-alice"
    assert store.load_refresh_token("bob@example.com") == "rt-bob"
    store.clear_refresh_token("alice@example.com")
    assert store.load_refresh_token("alice@example.com") is None
    assert store.load_refresh_token("bob@example.com") == "rt-bob"


def test_save_uses_default_service_name(
    fake_keyring: _FakeKeyringModule,
) -> None:
    """Default service name pins the keychain entry to this app."""
    from lap_coach_logger.infra.token_store import TokenStore

    store = TokenStore(keyring_module=fake_keyring)
    store.save_refresh_token(account="u@example.com", refresh_token="rt")

    assert ("lap-coach-logger", "u@example.com") in fake_keyring._store


def test_custom_service_name_is_honoured(
    fake_keyring: _FakeKeyringModule,
) -> None:
    """Tests/dev builds can scope to a different keychain namespace."""
    from lap_coach_logger.infra.token_store import TokenStore

    store = TokenStore(service_name="lap-coach-logger-dev", keyring_module=fake_keyring)
    store.save_refresh_token(account="u@example.com", refresh_token="rt")

    assert ("lap-coach-logger-dev", "u@example.com") in fake_keyring._store
    assert ("lap-coach-logger", "u@example.com") not in fake_keyring._store


def test_overwriting_a_token_is_allowed(
    fake_keyring: _FakeKeyringModule,
) -> None:
    """Token rotation: saving again must replace, not error."""
    from lap_coach_logger.infra.token_store import TokenStore

    store = TokenStore(keyring_module=fake_keyring)
    store.save_refresh_token(account="u@example.com", refresh_token="rt-old")
    store.save_refresh_token(account="u@example.com", refresh_token="rt-new")

    assert store.load_refresh_token("u@example.com") == "rt-new"


def test_default_keyring_module_is_real_keyring_when_not_injected() -> None:
    """If no module is injected, the store uses the real ``keyring`` library.

    This pins the prod-vs-test seam: prod code never has to inject anything;
    tests always do.
    """
    import keyring as real_keyring

    from lap_coach_logger.infra.token_store import TokenStore

    store = TokenStore()

    assert store._keyring is real_keyring  # type: ignore[attr-defined]
