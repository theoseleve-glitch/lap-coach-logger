"""Product analytics dispatch — the safe wrapper around ``posthog.capture``.

Module-level state mirrors the PostHog SDK's own shape: the
bootstrap calls :func:`configure` once with a distinct_id +
posthog module + enabled flag, and every subsequent
:func:`track` call is a one-line dispatch site (T060–T064).

Invariants:

* :func:`track` is **always safe** — it never raises, regardless of
  state. Analytics are advisory; a network blip or a missing SDK
  must never crash the app.
* :func:`configure` is idempotent and resettable, so the wiring can
  swap ``distinct_id`` from the anonymous install-id to the user's
  account email after Clerk pairing without any plumbing changes.
* :func:`get_or_create_install_id` returns a stable UUID across
  restarts so PostHog longitudinal funnels work on the same
  machine; corrupt / missing state files yield a fresh UUID rather
  than crashing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

log = logging.getLogger(__name__)

_active: bool = False
_distinct_id: str = ""
_posthog: Any | None = None


def configure(
    *,
    posthog_module: Any | None,
    distinct_id: str,
    enabled: bool = True,
) -> None:
    """Wire the analytics module to a configured PostHog SDK.

    Subsequent :func:`track` calls dispatch to ``posthog_module.capture``
    with the supplied ``distinct_id``. Pass ``enabled=False`` (or a
    ``posthog_module`` of ``None``) to put the module in safe-noop
    mode without unloading the existing wiring.
    """
    global _active, _distinct_id, _posthog
    _posthog = posthog_module
    _distinct_id = distinct_id
    _active = bool(enabled and posthog_module is not None)


def reset() -> None:
    """Restore the module to its un-configured state. For tests."""
    global _active, _distinct_id, _posthog
    _active = False
    _distinct_id = ""
    _posthog = None


def track(event_name: str, **properties: Any) -> None:
    """Fire a PostHog event, swallowing every error path.

    No-op when the module is un-configured, when ``enabled`` was
    False, when the SDK is missing, or when ``posthog.capture``
    raises. Properties are forwarded as-is.
    """
    if not _active or _posthog is None:
        return
    try:
        _posthog.capture(
            distinct_id=_distinct_id, event=event_name, properties=properties
        )
    except Exception:
        # Defensive: a bad SDK state must not bubble up. Log at
        # DEBUG only so the file log doesn't fill with analytics
        # noise during a network outage.
        log.debug("posthog.capture(%r) failed; dropping event", event_name)


# ---------------------------------------------------------------------------
# Persistent installation ID
# ---------------------------------------------------------------------------


def get_or_create_install_id(state_path: Path) -> str:
    """Return a stable per-installation UUID, persisting it on first call.

    A garbled file (e.g. a crashed write) is treated as a fresh
    install — the helper writes a new UUID and returns it. The
    keychain holds account credentials; this file only holds an
    anonymous identifier so losing it just resets analytics
    funnels for that machine, never breaks auth.
    """
    if state_path.exists():
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                cached = payload.get("install_id")
                if isinstance(cached, str) and cached:
                    return cached
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            pass  # fall through to mint a fresh one

    new_id = str(uuid4())
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"install_id": new_id}, indent=2), encoding="utf-8"
    )
    return new_id


__all__ = ["configure", "reset", "track", "get_or_create_install_id"]
