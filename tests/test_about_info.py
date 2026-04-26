"""T235: About dialog content builder.

Pins the dict the QML AboutDialog binds to. The QML pane just
displays whatever this helper returns, so testing the helper is
testing the contract for the dialog.

  - ``build_about_info()`` returns a dict with ``app_name``,
    ``app_version``, ``python_version``, ``qt_version``,
    ``os_summary``, ``dependencies``, and ``build_info``.
  - ``app_version`` matches ``lap_coach_logger.__version__``
    (single source of truth — no double-listed version string).
  - ``dependencies`` is a list of ``{"name": str, "version": str}``
    entries covering the headline runtime libraries the user
    might want to know about (Qt, pyarrow, pydantic, ...).
  - Missing dependencies (e.g. PySide6 not installed) report
    as ``"version": "not installed"`` rather than crashing the
    dialog.
  - ``build_info`` reports whether this is a frozen build
    (``sys.frozen``) or a dev run.
"""
from __future__ import annotations

import pytest

from lap_coach_logger import __version__ as APP_VERSION
from lap_coach_logger.diagnostics import about_info as ai


# ---------------------------------------------------------------------------
# Top-level shape
# ---------------------------------------------------------------------------


def test_build_about_info_returns_dict() -> None:
    info = ai.build_about_info()
    assert isinstance(info, dict)


def test_about_info_keys_are_stable() -> None:
    """Pin the top-level keys so the QML binding doesn't
    silently break when a key is renamed."""
    info = ai.build_about_info()
    expected = {
        "app_name",
        "app_version",
        "python_version",
        "qt_version",
        "os_summary",
        "dependencies",
        "build_info",
    }
    assert set(info.keys()) == expected


# ---------------------------------------------------------------------------
# Individual fields
# ---------------------------------------------------------------------------


def test_about_info_app_name_is_lap_coach_logger() -> None:
    info = ai.build_about_info()
    assert info["app_name"] == "Lap Coach Logger"


def test_about_info_app_version_matches_package_version() -> None:
    """Single source of truth: the displayed version must
    match ``lap_coach_logger.__version__`` so users + support
    are reading the same string."""
    info = ai.build_about_info()
    assert info["app_version"] == APP_VERSION


def test_about_info_python_version_is_dotted_string() -> None:
    """e.g. '3.14.3' — not 'Python 3.14.3' (the QML label
    adds the 'Python' prefix)."""
    info = ai.build_about_info()
    parts = info["python_version"].split(".")
    assert len(parts) >= 2
    for p in parts[:2]:
        assert p.isdigit(), f"non-numeric version segment in {info['python_version']!r}"


def test_about_info_os_summary_non_empty() -> None:
    info = ai.build_about_info()
    assert isinstance(info["os_summary"], str)
    assert info["os_summary"]


# ---------------------------------------------------------------------------
# Dependencies list
# ---------------------------------------------------------------------------


def test_about_info_dependencies_is_list_of_records() -> None:
    info = ai.build_about_info()
    deps = info["dependencies"]
    assert isinstance(deps, list)
    for dep in deps:
        assert isinstance(dep, dict)
        assert set(dep.keys()) == {"name", "version"}
        assert isinstance(dep["name"], str)
        assert isinstance(dep["version"], str)


def test_about_info_dependencies_includes_pyside_or_qt() -> None:
    """The Qt version is the most user-relevant dependency
    — most "looks weird" support tickets correlate with Qt
    version. Pin that it's listed."""
    info = ai.build_about_info()
    names = {d["name"] for d in info["dependencies"]}
    assert any("PySide6" in n or "Qt" in n for n in names), (
        f"expected PySide6 or Qt in deps; got {sorted(names)}"
    )


def test_about_info_dependencies_includes_pyarrow() -> None:
    """pyarrow drives Parquet writes — its version is load-
    bearing for writer-related issues."""
    info = ai.build_about_info()
    names = {d["name"].lower() for d in info["dependencies"]}
    assert "pyarrow" in names


def test_about_info_handles_missing_optional_dependency_gracefully() -> None:
    """A dep that isn't installed reports as 'not installed'
    rather than raising. Catches the case where a fresh
    install in a stripped venv (no pyirsdk, etc.) would
    crash the About dialog."""
    deps = ai.build_dependencies_list(("definitely_not_a_real_package_xyz_123",))
    assert len(deps) == 1
    assert deps[0]["name"] == "definitely_not_a_real_package_xyz_123"
    assert deps[0]["version"] == "not installed"


def test_about_info_handles_present_dependency() -> None:
    """A dep that IS installed reports its actual version
    string (non-empty)."""
    # 'pytest' is definitely installed since this test is
    # running under pytest.
    deps = ai.build_dependencies_list(("pytest",))
    assert len(deps) == 1
    assert deps[0]["name"] == "pytest"
    assert deps[0]["version"] != "not installed"
    assert deps[0]["version"]  # non-empty


# ---------------------------------------------------------------------------
# Build info
# ---------------------------------------------------------------------------


def test_about_info_build_info_is_dict() -> None:
    info = ai.build_about_info()
    assert isinstance(info["build_info"], dict)


def test_about_info_build_info_records_frozen_state() -> None:
    """``frozen`` tells support whether this is a packaged
    release or a dev run (``python -m`` from source)."""
    info = ai.build_about_info()
    assert "frozen" in info["build_info"]
    assert isinstance(info["build_info"]["frozen"], bool)
