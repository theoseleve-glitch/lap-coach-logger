"""Tests for ServiceViewModel — QML bridge over DesktopService state."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.qt_mock import FakeSignalInstance as _FakeSignalInstance, install
install()

from lap_coach_logger.viewmodels.service_vm import ServiceViewModel  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service_mock() -> MagicMock:
    """Return a mock that looks enough like DesktopService for the VM."""
    svc = MagicMock()
    # Service signals are plain objects (not descriptors) so use instances.
    svc.snapshot_changed = _FakeSignalInstance()
    svc.action_message = _FakeSignalInstance()
    svc.action_failed = _FakeSignalInstance()
    svc.settings_saved = _FakeSignalInstance()
    svc.settings_failed = _FakeSignalInstance()
    return svc


def _make_snapshot(**overrides: object) -> dict:
    """Build a realistic snapshot dict with sensible defaults."""
    # Defaults here match the VM's initial state so that passing a key
    # with the same default value does NOT trigger a change signal.
    base: dict[str, object] = {
        "status": "Idle",
        "status_detail": "",
        "is_monitoring": False,
        "sim": None,
        "elapsed_s": 0,
        "sample_count": 0,
        "sample_rate_hz_est": 0.0,
        "live": {},
        "lap_times": [],
        "track": None,
        "car": None,
        "current_lap": 0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Default property values
# ---------------------------------------------------------------------------

class TestDefaultProperties:
    """Before any snapshot arrives, properties should have safe defaults."""

    def test_status_default(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        assert vm.status == "Idle"

    def test_status_detail_default(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        assert vm.statusDetail == ""

    def test_is_monitoring_default(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        assert vm.isMonitoring is False

    def test_sim_default(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        assert vm.sim == ""

    def test_elapsed_seconds_default(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        assert vm.elapsedSeconds == 0

    def test_elapsed_formatted_default(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        assert vm.elapsedFormatted == "0:00"

    def test_greeting_returns_string(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        assert vm.greeting in ("Good morning", "Good afternoon", "Good evening")

    def test_latest_snapshot_is_none_initially(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        assert vm.latest_snapshot is None


# ---------------------------------------------------------------------------
# _on_snapshot updates properties
# ---------------------------------------------------------------------------

class TestOnSnapshotUpdates:
    """Calling _on_snapshot with a dict should update all derived props."""

    def test_status_updated(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(status="Recording"))
        assert vm.status == "Recording"

    def test_status_detail_updated(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(status_detail="iRacing - Spa - Lap 7"))
        assert vm.statusDetail == "iRacing - Spa - Lap 7"

    def test_is_monitoring_updated(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(is_monitoring=True))
        assert vm.isMonitoring is True

    def test_sim_updated(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(sim="iRacing"))
        assert vm.sim == "iRacing"

    def test_sim_none_becomes_empty_string(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(sim=None))
        assert vm.sim == ""

    def test_elapsed_seconds_updated(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(elapsed_s=1122))
        assert vm.elapsedSeconds == 1122

    def test_elapsed_formatted_minutes_seconds(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(elapsed_s=1122))
        assert vm.elapsedFormatted == "18:42"

    def test_elapsed_formatted_with_hours(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(elapsed_s=3661))
        assert vm.elapsedFormatted == "1:01:01"

    def test_elapsed_formatted_zero(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(elapsed_s=0))
        assert vm.elapsedFormatted == "0:00"

    def test_latest_snapshot_stored(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        snap = _make_snapshot(status="Recording", elapsed_s=42)
        vm._on_snapshot(snap)
        assert vm.latest_snapshot is snap


# ---------------------------------------------------------------------------
# Change signals fire only on actual changes
# ---------------------------------------------------------------------------

class TestChangeSignalDedup:
    """Signals should only emit when the property value actually changes."""

    def test_status_signal_fires_on_change(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(status="Recording"))
        assert vm.statusChanged.call_count == 1

    def test_status_signal_skipped_when_same(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(status="Idle"))  # same as default
        assert vm.statusChanged.call_count == 0

    def test_is_monitoring_signal_fires_on_change(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(is_monitoring=True))
        assert vm.isMonitoringChanged.call_count == 1

    def test_is_monitoring_signal_skipped_when_same(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(is_monitoring=False))
        assert vm.isMonitoringChanged.call_count == 0

    def test_sim_signal_fires_on_change(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(sim="ACC"))
        assert vm.simChanged.call_count == 1

    def test_sim_signal_skipped_when_same(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(sim=None))
        assert vm.simChanged.call_count == 0

    def test_elapsed_signal_fires_on_change(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(elapsed_s=10))
        assert vm.elapsedChanged.call_count == 1

    def test_elapsed_signal_skipped_when_same(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(elapsed_s=0))
        assert vm.elapsedChanged.call_count == 0

    def test_snapshot_signal_always_fires(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot())
        vm._on_snapshot(_make_snapshot())
        # snapshotChanged fires every time regardless
        assert vm.snapshotChanged.call_count == 2

    def test_multiple_changes_in_one_snapshot(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        vm._on_snapshot(_make_snapshot(
            status="Recording",
            is_monitoring=True,
            sim="iRacing",
            elapsed_s=60,
            status_detail="iRacing - Spa - Lap 1",
        ))
        assert vm.statusChanged.call_count == 1
        assert vm.isMonitoringChanged.call_count == 1
        assert vm.simChanged.call_count == 1
        assert vm.elapsedChanged.call_count == 1
        assert vm.statusDetailChanged.call_count == 1


# ---------------------------------------------------------------------------
# Slot delegation to service
# ---------------------------------------------------------------------------

class TestSlotDelegation:
    """Slots should forward calls to the underlying DesktopService."""

    def test_resume_monitoring(self) -> None:
        svc = _make_service_mock()
        vm = ServiceViewModel(svc)
        vm.resumeMonitoring()
        svc.start_monitoring.assert_called_once()

    def test_pause_monitoring(self) -> None:
        svc = _make_service_mock()
        vm = ServiceViewModel(svc)
        vm.pauseMonitoring()
        svc.stop_monitoring.assert_called_once()

    def test_open_output_folder(self) -> None:
        svc = _make_service_mock()
        vm = ServiceViewModel(svc)
        vm.openOutputFolder()
        svc.open_output_folder.assert_called_once()

    def test_open_logs_folder(self) -> None:
        svc = _make_service_mock()
        vm = ServiceViewModel(svc)
        vm.openLogsFolder()
        svc.open_logs_folder.assert_called_once()

    def test_open_config_folder(self) -> None:
        svc = _make_service_mock()
        vm = ServiceViewModel(svc)
        vm.openConfigFolder()
        svc.open_config_folder.assert_called_once()

    # T069 — Delete button wiring -----------------------------------------

    def test_delete_session_delegates_to_service(self) -> None:
        """``deleteSession(path)`` must forward to
        ``DesktopService.delete_review_session(path)`` so the bundle
        on disk + the sync queue entry are both cleaned up."""
        svc = _make_service_mock()
        vm = ServiceViewModel(svc)

        vm.deleteSession("C:/sessions/2026-04-25_Spa")

        svc.delete_review_session.assert_called_once_with(
            "C:/sessions/2026-04-25_Spa"
        )

    def test_delete_session_with_empty_path_is_a_safe_noop(self) -> None:
        """Defensive guard: a missing/empty path from QML must not
        trigger any delete (would no-op anyway, but the VM short-
        circuits to make intent clear)."""
        svc = _make_service_mock()
        vm = ServiceViewModel(svc)

        vm.deleteSession("")
        vm.deleteSession("   ")

        svc.delete_review_session.assert_not_called()

    def test_delete_session_emits_session_deleted_signal_on_success(self) -> None:
        """QML uses this signal to navigate away from the now-
        deleted review (otherwise the UI would still show the
        bundle's data after the underlying folder is gone)."""
        svc = _make_service_mock()
        vm = ServiceViewModel(svc)

        vm.deleteSession("C:/sessions/2026-04-25_Spa")

        assert vm.sessionDeleted.call_count == 1
        assert vm.sessionDeleted.call_args == (
            ("C:/sessions/2026-04-25_Spa",),
        )

    def test_delete_session_does_not_emit_signal_for_empty_path(self) -> None:
        svc = _make_service_mock()
        vm = ServiceViewModel(svc)

        vm.deleteSession("")

        assert vm.sessionDeleted.call_count == 0


# ---------------------------------------------------------------------------
# Greeting logic
# ---------------------------------------------------------------------------

class TestGreeting:
    """The greeting property should reflect the current time of day."""

    def test_morning(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        with patch("lap_coach_logger.viewmodels.service_vm._current_hour", return_value=8):
            assert vm.greeting == "Good morning"

    def test_afternoon(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        with patch("lap_coach_logger.viewmodels.service_vm._current_hour", return_value=14):
            assert vm.greeting == "Good afternoon"

    def test_evening(self) -> None:
        vm = ServiceViewModel(_make_service_mock())
        with patch("lap_coach_logger.viewmodels.service_vm._current_hour", return_value=20):
            assert vm.greeting == "Good evening"


# ---------------------------------------------------------------------------
# Service property
# ---------------------------------------------------------------------------

class TestServiceProperty:
    """The service property exposes the wrapped DesktopService."""

    def test_service_property_returns_injected_service(self) -> None:
        svc = _make_service_mock()
        vm = ServiceViewModel(svc)
        assert vm.service is svc
