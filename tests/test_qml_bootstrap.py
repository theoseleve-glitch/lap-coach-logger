"""Tests for qml_bootstrap.build_view_models -- ViewModel wiring layer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tests.qt_mock import FakeSignalInstance as _FakeSignalInstance, install
install(mock_gui=True)

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
    # Disable sync by default so tests do not spawn background threads.
    svc.config.sync.enabled = False
    svc.config.sync.api_url = ""
    svc.config.sync.device_token = ""
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
    """build_view_models must return a dict with all expected keys."""

    def test_returns_all_keys(self) -> None:
        vms = build_view_models(_make_service_mock())
        expected = {
            "service", "session", "history", "review", "settings", "overlay",
            "onboarding", "mode", "strategy", "syncStatus", "demo",
        }
        assert set(vms.keys()) == expected

    def test_returns_expected_entry_count(self) -> None:
        vms = build_view_models(_make_service_mock())
        assert len(vms) == 11


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
