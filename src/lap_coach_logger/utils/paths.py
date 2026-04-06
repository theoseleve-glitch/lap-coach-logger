"""Windows-aware path resolution for writable app directories.

All persistent data is stored under AppData regardless of source or packaged
execution mode. The application never relies on the current working directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from lap_coach_logger.app_identity import APP_DIR_NAME


def is_frozen() -> bool:
    """Return True when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def app_data_dir() -> Path:
    """Return LocalAppData app root for cache/log/runtime state."""
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / APP_DIR_NAME


def roaming_app_data_dir() -> Path:
    """Return RoamingAppData app root for config/state that should roam."""
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return base / APP_DIR_NAME


def cache_dir() -> Path:
    d = app_data_dir() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def runtime_dir() -> Path:
    d = app_data_dir() / "runtime"
    d.mkdir(parents=True, exist_ok=True)
    return d


def logs_dir() -> Path:
    d = app_data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_dir() -> Path:
    d = roaming_app_data_dir() / "config"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_file_path() -> Path:
    return config_dir() / "config.json"


def default_output_dir() -> Path:
    """Default session output: user's Documents/LapCoachLogger_sessions."""
    d = Path.home() / "Documents" / f"{APP_DIR_NAME}_sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def bundle_resource_path(relative: str) -> Path:
    """Resolve a bundled data file inside a PyInstaller package."""
    if is_frozen():
        # PyInstaller stores data files in sys._MEIPASS
        base = Path(getattr(sys, "_MEIPASS", "."))
    else:
        # Development mode: resolve from repository root in src layout.
        base = Path(__file__).resolve().parents[3]
    return base / relative
