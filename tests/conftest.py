"""Project-wide pytest fixtures providing ready-made telemetry samples and bundles.

These fixtures are available automatically to all test modules under tests/.
Shared helper functions live in tests/helpers.py so they can be imported by any
test module without going through conftest's special-file import mechanism.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lap_coach_logger.core.schema import TelemetrySample
from tests.helpers import finalize_session, make_quality_samples  # noqa: F401

# ---------------------------------------------------------------------------
# Qt mock isolation: collection ordering
# ---------------------------------------------------------------------------
# Some test modules (17 at time of writing — test_history_vm,
# test_session_vm, test_overlay_vm, test_strategy_vm, etc.) call
# qt_mock.install() at **module scope**, which permanently replaces
# sys.modules["PySide6.*"] with MagicMock objects. pytest's collection
# phase imports every test module up-front, so once one module has
# called install() the real PySide6 bindings are gone for the whole
# session.
#
# Tests that need the real PySide6 runtime
# (test_desktop_workspaces, test_overlay_browser_frontend,
# test_overlay_window_manager, test_ghost_widget) therefore need to be
# run in a separate pytest invocation:
#
#     pytest tests/test_desktop_workspaces.py tests/test_overlay_browser_frontend.py \
#            tests/test_overlay_window_manager.py tests/test_ghost_widget.py
#
# The ``pytest_collection_modifyitems`` below reorders items so that,
# within a single run, real-Qt tests execute first — which helps when
# the module-import side effect happens lazily but not when it fires
# at import time (the current case).
#
# **Exact next cleanup path** (deferred this sprint as not-low-risk —
# touches 17 files):
#   1. Move ``from tests.qt_mock import install; install()`` out of
#      module scope in each VM test file.
#   2. Replace with a pytest fixture (``@pytest.fixture(autouse=True)
#      def _qt_mock(): ...``) that installs lazily and that can be
#      opted out of per-module.
#   3. Each VM test file imports ViewModel classes inside the fixture
#      (or inside individual tests) rather than at module top.
# Until that refactor lands, run real-Qt tests in a separate
# invocation.
# ---------------------------------------------------------------------------

# Files that exercise real PySide6 QWidget machinery. These must run
# before any qt_mock.install() pollutes sys.modules.
_REAL_QT_TEST_FILES = frozenset({
    "test_desktop_workspaces.py",
    "test_overlay_browser_frontend.py",
    "test_overlay_window_manager.py",
    "test_ghost_widget.py",
    "test_overlay_runtime_instances.py",
    "test_overlay_workspace_shell.py",
    "test_overlay_browser.py",
    "test_overlay_settings_schema.py",
    "test_overlay_platform.py",
    "test_overlay_persistence_store.py",
    "test_overlay_layouts.py",
    "test_overlay_entitlements.py",
    "test_overlay_telemetry_bindings.py",
})


def pytest_collection_modifyitems(config, items):
    """Reorder tests so real-Qt modules run before qt_mock pollutes sys.modules."""
    def is_real_qt(item) -> bool:
        return Path(str(item.fspath)).name in _REAL_QT_TEST_FILES
    items.sort(key=lambda item: 0 if is_real_qt(item) else 1)

__all__ = ["make_quality_samples", "finalize_session"]


@pytest.fixture
def quality_samples() -> list[TelemetrySample]:
    """200 high-quality iRacing samples that pass all quality gates."""
    return make_quality_samples()


@pytest.fixture
def bundled_session(tmp_path: Path) -> Path:
    """A complete finalized iRacing session bundle under a fresh tmp directory."""
    output_root = tmp_path / "sessions"
    output_root.mkdir(parents=True)
    return finalize_session(output_root, session_uid="fixture-uid")
