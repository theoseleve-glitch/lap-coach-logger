"""Tests for qml_bootstrap.build_view_models -- ViewModel wiring layer."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# PySide6 may not be installed in the test environment.  We mock the Qt
# modules so the ViewModel source can be imported without a real Qt runtime.
# ---------------------------------------------------------------------------

_qt_core_mock = MagicMock()


class _FakeSignalInstance:
    """Per-object signal instance that records emit() and connect() calls."""

    def __init__(self) -> None:
        self._mock = MagicMock()
        self._connections: list = []

    def emit(self, *args: object) -> None:
        self._mock(*args)

    def connect(self, slot: object) -> None:
        self._connections.append(slot)

    @property
    def call_count(self) -> int:
        return self._mock.call_count


class _FakeSignal:
    """Descriptor that yields a fresh _FakeSignalInstance per owner object."""

    def __init__(self, *_args: object) -> None:
        self._name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, obj: object, objtype: type | None = None) -> _FakeSignal | _FakeSignalInstance:
        if obj is None:
            return self
        attr = f"_sig_{self._name}"
        inst = obj.__dict__.get(attr)
        if inst is None:
            inst = _FakeSignalInstance()
            obj.__dict__[attr] = inst
        return inst


class _FakeQObject:
    def __init__(self, *_a: object, **_kw: object) -> None:
        pass


_qt_core_mock.QObject = _FakeQObject
_qt_core_mock.Signal = _FakeSignal
_qt_core_mock.Slot = lambda *a, **kw: (lambda fn: fn)  # noqa: ARG005
_qt_core_mock.Property = lambda *a, **kw: property(kw.get("fget", lambda s: None))  # noqa: ARG005

sys.modules.setdefault("PySide6", MagicMock())
sys.modules.setdefault("PySide6.QtCore", _qt_core_mock)
sys.modules.setdefault("PySide6.QtGui", MagicMock())
sys.modules.setdefault("PySide6.QtQml", MagicMock())
sys.modules.setdefault("PySide6.QtWidgets", MagicMock())

from lap_coach_logger.viewmodels import (  # noqa: E402
    HistoryViewModel,
    OnboardingViewModel,
    OverlayViewModel,
    ReviewViewModel,
    ServiceViewModel,
    SessionViewModel,
    SettingsViewModel,
)
from lap_coach_logger.qml_bootstrap import build_view_models  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service_mock() -> MagicMock:
    """Return a mock that looks enough like DesktopService for build_view_models."""
    svc = MagicMock()
    svc.snapshot_changed = _FakeSignalInstance()
    svc.history_changed = _FakeSignalInstance()
    svc.review_changed = _FakeSignalInstance()
    svc.settings_saved = _FakeSignalInstance()
    svc.settings_failed = _FakeSignalInstance()
    svc.action_message = _FakeSignalInstance()
    svc.action_failed = _FakeSignalInstance()
    svc.settings_snapshot.return_value = {
        "output_dir": "C:/sessions",
        "sample_rate_hz": 10.0,
        "min_duration_s": 30,
        "min_samples": 50,
        "disconnect_timeout_s": 5.0,
        "enable_iracing": True,
        "enable_acc": True,
        "start_with_windows": False,
        "debug_csv": False,
    }
    return svc


# ---------------------------------------------------------------------------
# build_view_models returns correct keys
# ---------------------------------------------------------------------------

class TestBuildViewModelsKeys:
    """build_view_models must return a dict with all 7 expected keys."""

    def test_returns_all_seven_keys(self) -> None:
        vms = build_view_models(_make_service_mock())
        expected = {"service", "session", "history", "review", "settings", "overlay", "onboarding"}
        assert set(vms.keys()) == expected

    def test_returns_exactly_seven_entries(self) -> None:
        vms = build_view_models(_make_service_mock())
        assert len(vms) == 7


# ---------------------------------------------------------------------------
# build_view_models returns correct ViewModel types
# ---------------------------------------------------------------------------

class TestBuildViewModelsTypes:
    """Each value in the returned dict must be the correct ViewModel type."""

    def test_service_vm_type(self) -> None:
        vms = build_view_models(_make_service_mock())
        assert isinstance(vms["service"], ServiceViewModel)

    def test_session_vm_type(self) -> None:
        vms = build_view_models(_make_service_mock())
        assert isinstance(vms["session"], SessionViewModel)

    def test_history_vm_type(self) -> None:
        vms = build_view_models(_make_service_mock())
        assert isinstance(vms["history"], HistoryViewModel)

    def test_review_vm_type(self) -> None:
        vms = build_view_models(_make_service_mock())
        assert isinstance(vms["review"], ReviewViewModel)

    def test_settings_vm_type(self) -> None:
        vms = build_view_models(_make_service_mock())
        assert isinstance(vms["settings"], SettingsViewModel)

    def test_overlay_vm_type(self) -> None:
        vms = build_view_models(_make_service_mock())
        assert isinstance(vms["overlay"], OverlayViewModel)

    def test_onboarding_vm_type(self) -> None:
        vms = build_view_models(_make_service_mock())
        assert isinstance(vms["onboarding"], OnboardingViewModel)


# ---------------------------------------------------------------------------
# build_view_models performs initial settings load
# ---------------------------------------------------------------------------

class TestBuildViewModelsInitialLoad:
    """build_view_models must call service.settings_snapshot() for initial load."""

    def test_settings_snapshot_called(self) -> None:
        svc = _make_service_mock()
        build_view_models(svc)
        svc.settings_snapshot.assert_called_once()

    def test_settings_vm_has_initial_values(self) -> None:
        svc = _make_service_mock()
        vms = build_view_models(svc)
        # The settings VM should have been loaded with the snapshot values.
        assert vms["settings"].values.get("output_dir") == "C:/sessions"


# ---------------------------------------------------------------------------
# build_view_models wires signal connections
# ---------------------------------------------------------------------------

class TestBuildViewModelsWiring:
    """build_view_models must wire service signals to child VMs."""

    def test_snapshot_changed_has_connections(self) -> None:
        svc = _make_service_mock()
        build_view_models(svc)
        # snapshot_changed should be connected to session_vm and overlay_vm
        assert len(svc.snapshot_changed._connections) >= 2

    def test_history_changed_has_connection(self) -> None:
        svc = _make_service_mock()
        build_view_models(svc)
        assert len(svc.history_changed._connections) >= 1

    def test_review_changed_has_connection(self) -> None:
        svc = _make_service_mock()
        build_view_models(svc)
        assert len(svc.review_changed._connections) >= 1

    def test_settings_saved_has_connection(self) -> None:
        svc = _make_service_mock()
        build_view_models(svc)
        assert len(svc.settings_saved._connections) >= 1
