"""Webapp URL builder — used by "View in webapp" CTAs.

Per Q95 (and ADR-002's repo split), the desktop pushes export and
deep-analysis flows to the lap-webapp Next.js app. The desktop
side just needs a URL builder; ``url_opener`` injection at the
slot layer (``ServiceViewModel.viewSessionInWebapp``) keeps the
"actually launch a browser" side testable.

Base URL priority: ``LAP_COACH_WEBAPP_URL`` env var > prod default.
This matches the SENTRY_DSN / POSTHOG_API_KEY pattern from Block D
so staging / dev builds point at non-prod webapps without code
changes.
"""

from __future__ import annotations

import os

_DEFAULT_WEBAPP_URL = "https://app.lap-coach.racing"
_SESSIONS_PATH = "/sessions"


def webapp_base_url() -> str:
    """Return the configured webapp root, normalised (no trailing slash)."""
    raw = os.environ.get("LAP_COACH_WEBAPP_URL", "").strip()
    return (raw or _DEFAULT_WEBAPP_URL).rstrip("/")


def view_sessions_url() -> str:
    """URL for the webapp sessions list — the safe default CTA target
    when no specific session_id is known."""
    return f"{webapp_base_url()}{_SESSIONS_PATH}"


def view_session_url(session_id: str) -> str:
    """URL for a specific session detail page.

    A blank / whitespace-only ``session_id`` falls back to
    :func:`view_sessions_url` rather than producing a URL with an
    empty trailing segment (which would 404 on the webapp).
    """
    sid = (session_id or "").strip()
    if not sid:
        return view_sessions_url()
    return f"{webapp_base_url()}{_SESSIONS_PATH}/{sid}"


__all__ = ["webapp_base_url", "view_sessions_url", "view_session_url"]
