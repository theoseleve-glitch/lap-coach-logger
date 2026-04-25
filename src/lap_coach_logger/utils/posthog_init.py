"""PostHog SDK bootstrap helper.

Wires ``posthog`` into the desktop so subsequent product analytics
events (T060+) reach PostHog. The actual ``capture()`` call sites
land in later sprint tasks; this module ships the initialization
contract only.

The contract mirrors :mod:`utils.sentry_init` so T065's user opt-out
flag can plug into both telemetry providers with the same
``enabled=`` argument:

  * No API key anywhere     -> no-op (False).  Dev / unconfigured CI.
  * ``enabled=False``       -> no-op (False).  T065 opt-out plug.
  * posthog missing/broken  -> no-op (False).  Bundle hardening.
  * SDK init raises         -> no-op (False).  Misconfig must not
                               block bootstrap.
  * Otherwise               -> set ``module.api_key`` (and optionally
                               ``module.host``), return True.

API key priority: explicit kwarg > ``POSTHOG_API_KEY`` env var.
Host priority:    explicit kwarg > ``POSTHOG_HOST`` env var > omitted
(in which case the SDK keeps its own default).
"""

from __future__ import annotations

import os
from typing import Any


def init_posthog(
    *,
    api_key: str | None = None,
    host: str | None = None,
    enabled: bool = True,
    posthog_module: Any | None = None,
) -> bool:
    """Initialize PostHog. Returns ``True`` iff the SDK was wired up.

    Parameters
    ----------
    api_key:
        PostHog project API key. Falls back to ``POSTHOG_API_KEY``.
        Without one, the helper returns ``False`` and the module is
        not mutated.
    host:
        Optional self-hosted PostHog host. Falls back to
        ``POSTHOG_HOST``. Omitted attribute writes when neither is
        set so the SDK's own default host stays in effect.
    enabled:
        Master switch. T065 user opt-out plug.
    posthog_module:
        Override the imported ``posthog`` module. Tests inject a
        fake; prod uses the real package.
    """
    if not enabled:
        return False

    effective_key = (api_key or os.environ.get("POSTHOG_API_KEY", "")).strip()
    if not effective_key:
        return False

    module = posthog_module if posthog_module is not None else _import_posthog()
    if module is None or not hasattr(module, "api_key"):
        return False

    effective_host = (host or os.environ.get("POSTHOG_HOST", "")).strip()

    try:
        module.api_key = effective_key
        if effective_host:
            module.host = effective_host
    except Exception:
        # Defensive: some module-level setters could raise on bad
        # input. A misconfigured analytics provider must never block
        # the app from starting.
        return False
    return True


def _import_posthog() -> Any | None:
    """Return the real ``posthog`` module, or ``None`` if absent."""
    try:
        import posthog  # type: ignore[import-not-found]
    except ImportError:
        return None
    return posthog


__all__ = ["init_posthog"]
