"""Support-email mailto: helpers (T234).

Builds the ``mailto:`` URL the Help menu opens. Pure helper so
we can pin contract (URL shape, prefilled diagnostic context,
encoding) in CI without spinning up the Qt menu, and so the
same URL can be re-used in the AboutDialog or first-run
consent screen later.
"""
from __future__ import annotations

import platform
from urllib.parse import urlencode

from lap_coach_logger import __version__ as _APP_VERSION

SUPPORT_EMAIL: str = "support@lap-coach.racing"

_BODY_TEMPLATE = (
    "Please describe the issue you ran into:\n"
    "\n"
    "(your description here)\n"
    "\n"
    "----\n"
    "Diagnostic context\n"
    "----\n"
    "App version: {app_version}\n"
    "Operating system: {os_summary}\n"
)


def build_support_mailto(
    *,
    app_version: str,
    os_summary: str,
    app_name: str = "Lap Coach Logger",
) -> str:
    """Build a ``mailto:`` URL for opening a fresh support email.

    The query string carries:
      - ``subject``: identifies the product so triage is fast
      - ``body``: prefilled with app version + OS summary + a
        "describe what happened" placeholder so the first
        reply already has the basics

    Special characters in any field are URL-encoded so the
    mail client doesn't see a malformed URL.
    """
    subject = f"{app_name} support"
    body = _BODY_TEMPLATE.format(
        app_version=app_version,
        os_summary=os_summary,
    )
    # quote_via=quote so spaces become %20 (compatible with
    # mailto: handlers across Windows / macOS / Linux).
    from urllib.parse import quote
    query = urlencode({"subject": subject, "body": body}, quote_via=quote)
    return f"mailto:{SUPPORT_EMAIL}?{query}"


def _current_os_summary() -> str:
    """Best-effort one-line OS description for the body."""
    try:
        sysname = platform.system() or "Unknown"
        release = platform.release() or ""
        version = platform.version() or ""
        if version:
            return f"{sysname} {release} ({version})"
        return f"{sysname} {release}".strip()
    except Exception:
        return "Unknown"


def build_default_support_mailto() -> str:
    """Convenience wrapper used by Help-menu call sites that
    don't have explicit context — auto-fills app version and
    OS summary from the current process."""
    return build_support_mailto(
        app_version=_APP_VERSION,
        os_summary=_current_os_summary(),
    )


__all__ = [
    "SUPPORT_EMAIL",
    "build_support_mailto",
    "build_default_support_mailto",
]
