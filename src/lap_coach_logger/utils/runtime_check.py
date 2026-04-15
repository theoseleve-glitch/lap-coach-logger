"""Runtime version validation.

Warns when running on an unsupported Python version so log spam,
traceback display quirks, and untested library behavior don't
silently surface in production.
"""
from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)

_REQUIRED_MAJOR = 3
_REQUIRED_MINOR = 12


def check_runtime(strict: bool = False) -> bool:
    """Return True if running on a supported Python version.

    Logs a warning for minor-version mismatch, raises RuntimeError
    when strict=True and mismatch is detected.
    """
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) == (_REQUIRED_MAJOR, _REQUIRED_MINOR):
        return True
    message = (
        f"Unsupported Python version {major}.{minor}.x "
        f"(required: {_REQUIRED_MAJOR}.{_REQUIRED_MINOR}.x). "
        "Traceback display, signal dispatch, and Qt integration "
        "may behave unexpectedly."
    )
    if strict:
        raise RuntimeError(message)
    log.warning(message)
    return False


def current_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
