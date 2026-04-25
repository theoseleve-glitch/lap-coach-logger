"""Keychain-backed storage for Clerk refresh tokens.

ADR-011 mandates that desktop stores Clerk refresh tokens in the
host OS keychain (Windows Credential Manager / macOS Keychain /
Linux Secret Service / KWallet). This module wraps the ``keyring``
library so the rest of the app depends on a stable interface and
tests can inject a fake backend without touching the real keychain.

Account is currently the user's email — the natural Clerk identity
key. Service name pins entries to this app so multiple Clerk-using
apps on the same host don't collide. Token rotation is handled by
``set_password`` semantics (overwrite-on-set).
"""

from __future__ import annotations

from typing import Any

import keyring as _real_keyring

_DEFAULT_SERVICE_NAME = "lap-coach-logger"


class TokenStore:
    """Thin facade over the OS keychain for Clerk refresh tokens.

    Parameters
    ----------
    service_name:
        Keychain "service" string. Defaults to ``"lap-coach-logger"``;
        dev/staging builds can override (e.g. ``"lap-coach-logger-dev"``)
        so they don't clobber a user's prod entry.
    keyring_module:
        Anything that exposes the ``keyring`` module-level surface
        (``set_password`` / ``get_password`` / ``delete_password``
        plus an ``errors.PasswordDeleteError`` exception class).
        Defaults to the real ``keyring`` library; tests inject a
        fake.
    """

    def __init__(
        self,
        *,
        service_name: str = _DEFAULT_SERVICE_NAME,
        keyring_module: Any | None = None,
    ) -> None:
        self._service_name = service_name
        self._keyring = keyring_module if keyring_module is not None else _real_keyring

    def save_refresh_token(self, *, account: str, refresh_token: str) -> None:
        """Persist (or overwrite) the refresh token for ``account``."""
        self._keyring.set_password(self._service_name, account, refresh_token)

    def load_refresh_token(self, account: str) -> str | None:
        """Return the stored refresh token, or ``None`` if not present."""
        return self._keyring.get_password(self._service_name, account)

    def clear_refresh_token(self, account: str) -> None:
        """Remove the stored token. Safe to call when nothing is stored."""
        delete_error_cls = getattr(
            self._keyring.errors, "PasswordDeleteError", Exception
        )
        try:
            self._keyring.delete_password(self._service_name, account)
        except delete_error_cls:
            # No entry to clear — treat as success so callers don't
            # have to track existence themselves.
            return


__all__ = ["TokenStore"]
