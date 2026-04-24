"""Regression test: all VM classes importable via bootstrap (sprint T011).

Locks in the contract that ``qml_bootstrap.build_view_models`` wires
every ViewModel type the QML shell binds to — a missing or unimportable
VM here would silently break the app at startup. Complements
``test_qml_bootstrap.py`` which focuses on specific-key assertions.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from tests.qt_mock import FakeSignalInstance as _FakeSignalInstance, install

install(mock_gui=True)


_EXPECTED_TYPES: dict[str, str] = {
    "service": "ServiceViewModel",
    "session": "SessionViewModel",
    "history": "HistoryViewModel",
    "review": "ReviewViewModel",
    "settings": "SettingsViewModel",
    "overlay": "OverlayViewModel",
    "onboarding": "OnboardingViewModel",
    "mode": "ModeViewModel",
    "strategy": "StrategyViewModel",
    "syncStatus": "SyncStatusViewModel",
    "demo": "DemoViewModel",
}


def _service_mock() -> MagicMock:
    svc = MagicMock()
    svc.snapshot_changed = _FakeSignalInstance()
    svc.history_changed = _FakeSignalInstance()
    svc.review_changed = _FakeSignalInstance()
    svc.settings_saved = _FakeSignalInstance()
    svc.settings_failed = _FakeSignalInstance()
    svc.action_message = _FakeSignalInstance()
    svc.action_failed = _FakeSignalInstance()
    svc.config.sync.enabled = False
    svc.config.sync.api_url = ""
    svc.config.sync.device_token = ""
    svc.settings_snapshot.return_value = {}
    return svc


def test_bootstrap_build_view_models_includes_every_expected_vm() -> None:
    from lap_coach_logger.qml_bootstrap import build_view_models

    vms = build_view_models(_service_mock())
    assert set(vms.keys()) == set(_EXPECTED_TYPES.keys())


def test_each_vm_has_expected_class_name() -> None:
    from lap_coach_logger.qml_bootstrap import build_view_models

    vms = build_view_models(_service_mock())
    for key, expected_cls in _EXPECTED_TYPES.items():
        actual_cls = type(vms[key]).__name__
        assert actual_cls == expected_cls, (
            f"vms[{key!r}] is {actual_cls}, expected {expected_cls}"
        )


def test_bootstrap_imports_every_vm_module_without_error() -> None:
    # Importing qml_bootstrap re-exports the VM import graph. Any VM
    # module with a broken import (missing symbol, property collision,
    # circular import) would raise here.
    import importlib

    module = importlib.import_module("lap_coach_logger.qml_bootstrap")
    assert hasattr(module, "build_view_models")
