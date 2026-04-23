"""Release vs development build detection.

Release (PyInstaller) builds run under pinned Python 3.12 and should
refuse to start on any other interpreter — silent traceback-misattribution
bugs on 3.14 (see logging_setup.py) are unacceptable in shipped binaries.

Development launches (`python -m lap_coach_logger`) stay permissive so
contributors can run on whatever interpreter they have locally; they only
get a warning from :func:`check_runtime`.

``IS_FROZEN`` is True when running from a PyInstaller bundle. The attribute
``sys.frozen`` is set by the bootloader; absence means we're in a regular
interpreter. This is the canonical check recommended by PyInstaller docs.
"""

from __future__ import annotations

import sys

IS_FROZEN: bool = getattr(sys, "frozen", False)
"""True when running from a PyInstaller bundle, False in dev."""

BUILD_KIND: str = "release" if IS_FROZEN else "development"
"""Human-readable label for logs and diagnostics."""
