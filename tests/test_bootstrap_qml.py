"""Tests for bootstrap QML shell wiring."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Ensure PySide6 mocks are available so bootstrap can be imported
# without a real Qt runtime.
sys.modules.setdefault("PySide6", MagicMock())
sys.modules.setdefault("PySide6.QtCore", MagicMock())
sys.modules.setdefault("PySide6.QtGui", MagicMock())
sys.modules.setdefault("PySide6.QtQml", MagicMock())
sys.modules.setdefault("PySide6.QtWidgets", MagicMock())


def test_bootstrap_imports_qml_shell():
    import lap_coach_logger.bootstrap as bootstrap_mod
    assert hasattr(bootstrap_mod, "run_qml_shell") or "run_qml_shell" in dir(bootstrap_mod)


def test_bootstrap_does_not_import_old_desktop_shell():
    import lap_coach_logger.bootstrap as bootstrap_mod
    # The old QWidgets shell should no longer be referenced.
    assert not hasattr(bootstrap_mod, "run_desktop_shell")
