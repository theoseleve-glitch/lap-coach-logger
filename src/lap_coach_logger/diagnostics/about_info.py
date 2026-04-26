"""About-dialog content builder (T235).

Pure helper that produces the dict the QML AboutDialog binds
to. Putting this here means we can pin contract (top-level
keys, dependency-list shape, missing-dep handling) in CI
without instantiating the dialog.

The dict shape is the public contract — renaming a key without
updating the QML binding silently breaks the dialog, so the
test that pins the key set is load-bearing.
"""
from __future__ import annotations

import importlib.metadata
import platform
import sys
from typing import Any

from lap_coach_logger import __version__ as _APP_VERSION


_HEADLINE_DEPS: tuple[str, ...] = (
    "PySide6",
    "pyarrow",
    "pydantic",
    "transitions",
    "requests",
    "cryptography",
    "pyirsdk",
)


def build_dependencies_list(names: tuple[str, ...]) -> list[dict[str, str]]:
    """Resolve each package name via importlib.metadata.
    A package that isn't installed reports as ``"not installed"``
    rather than raising — the About dialog must keep working
    even on a stripped venv."""
    out: list[dict[str, str]] = []
    for name in names:
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            version = "not installed"
        except Exception:
            # Defensive: never let metadata lookup crash the dialog.
            version = "unknown"
        out.append({"name": name, "version": version})
    return out


def _qt_version_string() -> str:
    """PySide6 version (which dictates Qt version). Reports
    'not installed' when PySide6 isn't on the system."""
    try:
        return importlib.metadata.version("PySide6")
    except importlib.metadata.PackageNotFoundError:
        return "not installed"
    except Exception:
        return "unknown"


def _os_summary() -> str:
    """One-line OS description for the dialog."""
    try:
        sysname = platform.system() or "Unknown"
        release = platform.release() or ""
        version = platform.version() or ""
        if version:
            return f"{sysname} {release} ({version})"
        return f"{sysname} {release}".strip()
    except Exception:
        return "Unknown"


def build_about_info() -> dict[str, Any]:
    """Return the dict the QML AboutDialog binds to.

    Top-level keys (stable contract):
      - ``app_name``: human-readable product name
      - ``app_version``: matches ``lap_coach_logger.__version__``
      - ``python_version``: dotted version string (no prefix)
      - ``qt_version``: PySide6/Qt version
      - ``os_summary``: one-line OS description
      - ``dependencies``: list of ``{"name": str, "version": str}``
      - ``build_info``: dict with at least ``frozen: bool``
    """
    return {
        "app_name": "Lap Coach Logger",
        "app_version": _APP_VERSION,
        "python_version": platform.python_version(),
        "qt_version": _qt_version_string(),
        "os_summary": _os_summary(),
        "dependencies": build_dependencies_list(_HEADLINE_DEPS),
        "build_info": {
            "frozen": bool(getattr(sys, "frozen", False)),
        },
    }


__all__ = ["build_about_info", "build_dependencies_list"]
