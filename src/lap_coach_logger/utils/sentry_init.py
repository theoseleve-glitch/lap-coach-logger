"""Sentry SDK bootstrap helper.

Wires ``sentry-sdk`` into the desktop so unhandled exceptions land
in Sentry. The actual capture/transport machinery is the SDK's
problem; our concern is the **initialization contract**:

  * No DSN anywhere     -> no-op (local dev / unconfigured CI).
  * ``enabled=False``   -> no-op (T065 user opt-out).
  * sentry-sdk missing  -> no-op (bundle hardening; bootstrap must
                          not crash if the optional dep was stripped).
  * Otherwise           -> ``sentry_sdk.init(dsn=..., environment=...,
                          release=...)`` and return ``True``.

The DSN, environment, and release are all optional and read in
this priority order: explicit kwarg > ``SENTRY_DSN`` env var (DSN
only) > omitted. Returning ``bool`` lets the caller log
"telemetry enabled" / "telemetry disabled" without inspecting
SDK internals.

Production wiring lives in ``bootstrap.py``; this module is a
plain function so it stays unit-testable without spinning up Qt.
"""

from __future__ import annotations

import os
from typing import Any


def init_sentry(
    *,
    dsn: str | None = None,
    environment: str | None = None,
    release: str | None = None,
    enabled: bool = True,
    sentry_module: Any | None = None,
) -> bool:
    """Initialize Sentry. Returns ``True`` iff the SDK was actually init'd.

    Parameters
    ----------
    dsn:
        Sentry DSN. Falls back to the ``SENTRY_DSN`` env var. When
        both are absent (or blank), Sentry stays off and the
        function returns ``False``.
    environment:
        Optional environment tag (``"production"`` / ``"staging"``).
        Omitted from the SDK call when ``None`` — Sentry treats an
        explicit ``None`` differently from "not specified".
    release:
        Optional release tag. T058 will populate this from
        ``__version__``.
    enabled:
        Master switch. When ``False`` (T065 user opt-out), Sentry
        stays off even if a DSN is configured.
    sentry_module:
        Override the imported ``sentry_sdk`` module. Tests inject
        a fake; prod uses the real package.
    """
    if not enabled:
        return False

    effective_dsn = (dsn or os.environ.get("SENTRY_DSN", "")).strip()
    if not effective_dsn:
        return False

    module = sentry_module if sentry_module is not None else _import_sentry_sdk()
    if module is None or not hasattr(module, "init"):
        return False

    init_kwargs: dict[str, Any] = {"dsn": effective_dsn}
    if environment is not None:
        init_kwargs["environment"] = environment
    if release is not None:
        init_kwargs["release"] = release

    try:
        module.init(**init_kwargs)
    except Exception:
        # Defensive: a misconfigured DSN must not block bootstrap.
        return False
    return True


def _import_sentry_sdk() -> Any | None:
    """Return the real ``sentry_sdk`` module, or ``None`` if absent."""
    try:
        import sentry_sdk  # type: ignore[import-not-found]
    except ImportError:
        return None
    return sentry_sdk


# Sentry's "Releases" feature groups errors by build identifier;
# the recommended format is ``<package>@<version>`` so events can be
# linked back to source maps / commits in CI integrations.
_RELEASE_PACKAGE = "lap-coach-logger"


def sentry_release_tag(version: str | None = None) -> str:
    """Return the Sentry-formatted release tag ``<package>@<version>``.

    With no explicit ``version``, the helper reads
    ``lap_coach_logger.__version__`` (sourced from
    ``app_identity.VERSION``) so a single bump there flows into
    every Sentry release tag without a second edit.
    """
    if version is None:
        from lap_coach_logger import __version__ as live_version
        version = live_version
    return f"{_RELEASE_PACKAGE}@{version}"


__all__ = ["init_sentry", "sentry_release_tag"]
