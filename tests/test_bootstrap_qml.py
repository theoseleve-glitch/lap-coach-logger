"""Tests for bootstrap QML shell wiring."""
from __future__ import annotations

from tests.qt_mock import install
install(mock_gui=True)


def test_bootstrap_imports_qml_shell():
    import lap_coach_logger.bootstrap as bootstrap_mod
    assert hasattr(bootstrap_mod, "run_qml_shell") or "run_qml_shell" in dir(bootstrap_mod)


def test_bootstrap_does_not_import_old_desktop_shell():
    import lap_coach_logger.bootstrap as bootstrap_mod
    # The old QWidgets shell should no longer be referenced.
    assert not hasattr(bootstrap_mod, "run_desktop_shell")
