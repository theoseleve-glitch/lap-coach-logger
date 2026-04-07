"""Integration smoke tests for the QML ViewModel layer.

Verifies that ``build_view_models`` wires all 7 ViewModels correctly and
that data flows end-to-end through the system: service -> VM -> properties.
"""

from __future__ import annotations

import subprocess
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
        # Propagate to connected slots so integration wiring works.
        for slot in self._connections:
            slot(*args)

    def connect(self, slot: object) -> None:
        self._connections.append(slot)

    @property
    def call_count(self) -> int:
        return self._mock.call_count

    @property
    def call_args(self):  # noqa: ANN204
        return self._mock.call_args

    @property
    def call_args_list(self):  # noqa: ANN204
        return self._mock.call_args_list


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
# Shared test data
# ---------------------------------------------------------------------------

SETTINGS_SNAPSHOT: dict = {
    "output_dir": "C:\\Users\\Test\\sessions",
    "driver_name": "Test Driver",
    "sample_rate_hz": 60.0,
    "enable_iracing": True,
    "enable_acc": True,
    "enable_assetto_corsa": False,
    "enable_lmu": False,
    "start_with_windows": False,
}

RECORDING_SNAPSHOT: dict = {
    "status": "Recording",
    "status_detail": "iRacing \u2014 Spa-Francorchamps \u2014 Lap 7",
    "is_monitoring": True,
    "sim": "iRacing",
    "track": "Spa-Francorchamps",
    "car": "Porsche 911 GT3 R",
    "current_lap": 7,
    "elapsed_s": 1234,
    "sample_count": 50000,
    "sample_rate_hz_est": 59.8,
    "live": {
        "speed_kph": 247.3,
        "throttle_pct": 0.87,
        "brake_pct": 0.0,
        "current_lap": 7,
    },
    "lap_times": [
        {"lap": 1, "time_s": 141.2, "sectors": [], "status": "clean"},
        {"lap": 2, "time_s": 139.8, "sectors": [], "status": "clean"},
        {"lap": 3, "time_s": 137.834, "sectors": [], "status": "clean"},
        {"lap": 4, "time_s": 138.091, "sectors": [], "status": "clean"},
    ],
}

SAMPLE_SESSIONS: list[dict] = [
    {
        "session_id": "int-001",
        "folder": "/sessions/2026-04-01_spa",
        "track": "Spa-Francorchamps",
        "car": "BMW M4 GT3",
        "sim": "iRacing",
    },
    {
        "session_id": "int-002",
        "folder": "/sessions/2026-04-02_monza",
        "track": "Monza",
        "car": "Ferrari 296 GT3",
        "sim": "ACC",
    },
    {
        "session_id": "int-003",
        "folder": "/sessions/2026-04-03_nords",
        "track": "Nordschleife",
        "car": "Porsche 911 GT3 R",
        "sim": "iRacing",
    },
]

SAMPLE_REVIEW: dict = {
    "folder": "/sessions/2026-04-01_spa",
    "track": "Spa-Francorchamps",
    "sim": "iRacing",
    "laps": [
        {"lap": 1, "time_s": 132.456, "status": "valid"},
        {"lap": 2, "time_s": 131.890, "status": "valid"},
    ],
    "quality": {"score": 0.95, "grade": "A"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_service() -> MagicMock:
    """Return a mock DesktopService with all signals needed by build_view_models."""
    svc = MagicMock()
    svc.snapshot_changed = _FakeSignalInstance()
    svc.history_changed = _FakeSignalInstance()
    svc.review_changed = _FakeSignalInstance()
    svc.review_requested = _FakeSignalInstance()
    svc.log_event = MagicMock()
    svc.settings_saved = _FakeSignalInstance()
    svc.settings_failed = _FakeSignalInstance()
    svc.action_message = _FakeSignalInstance()
    svc.action_failed = _FakeSignalInstance()
    svc.settings_snapshot.return_value = dict(SETTINGS_SNAPSHOT)
    return svc


# ---------------------------------------------------------------------------
# 1. All ViewModels instantiate via build_view_models
# ---------------------------------------------------------------------------

class TestAllViewModelsInstantiate:
    """build_view_models must return all 7 VMs with correct types."""

    def test_returns_all_seven_keys(self) -> None:
        vms = build_view_models(_mock_service())
        expected = {"service", "session", "history", "review", "settings", "overlay", "onboarding"}
        assert set(vms.keys()) == expected

    def test_returns_exactly_seven_entries(self) -> None:
        vms = build_view_models(_mock_service())
        assert len(vms) == 7

    def test_service_vm_type(self) -> None:
        vms = build_view_models(_mock_service())
        assert isinstance(vms["service"], ServiceViewModel)

    def test_session_vm_type(self) -> None:
        vms = build_view_models(_mock_service())
        assert isinstance(vms["session"], SessionViewModel)

    def test_history_vm_type(self) -> None:
        vms = build_view_models(_mock_service())
        assert isinstance(vms["history"], HistoryViewModel)

    def test_review_vm_type(self) -> None:
        vms = build_view_models(_mock_service())
        assert isinstance(vms["review"], ReviewViewModel)

    def test_settings_vm_type(self) -> None:
        vms = build_view_models(_mock_service())
        assert isinstance(vms["settings"], SettingsViewModel)

    def test_overlay_vm_type(self) -> None:
        vms = build_view_models(_mock_service())
        assert isinstance(vms["overlay"], OverlayViewModel)

    def test_onboarding_vm_type(self) -> None:
        vms = build_view_models(_mock_service())
        assert isinstance(vms["onboarding"], OnboardingViewModel)


# ---------------------------------------------------------------------------
# 2. Snapshot propagates to SessionViewModel
# ---------------------------------------------------------------------------

class TestSnapshotPropagatesToSessionVM:
    """Simulating a snapshot through service_vm and session_vm."""

    def test_service_vm_receives_snapshot(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["service"]._on_snapshot(RECORDING_SNAPSHOT)
        assert vms["service"].status == "Recording"
        assert vms["service"].sim == "iRacing"

    def test_session_vm_track_updated(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["session"].update_from_snapshot(RECORDING_SNAPSHOT)
        assert vms["session"].track == "Spa-Francorchamps"

    def test_session_vm_car_updated(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["session"].update_from_snapshot(RECORDING_SNAPSHOT)
        assert vms["session"].car == "Porsche 911 GT3 R"

    def test_session_vm_current_lap_updated(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["session"].update_from_snapshot(RECORDING_SNAPSHOT)
        assert vms["session"].currentLap == 7

    def test_session_vm_live_telemetry_updated(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["session"].update_from_snapshot(RECORDING_SNAPSHOT)
        assert vms["session"].speedKph == pytest.approx(247.3)
        assert vms["session"].throttlePct == pytest.approx(0.87)
        assert vms["session"].brakePct == pytest.approx(0.0)

    def test_session_vm_laps_populated(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["session"].update_from_snapshot(RECORDING_SNAPSHOT)
        assert len(vms["session"].laps) == 4

    def test_snapshot_signal_propagates_to_session_vm(self) -> None:
        """Emit on the service signal -> session_vm gets updated automatically."""
        svc = _mock_service()
        vms = build_view_models(svc)
        svc.snapshot_changed.emit(RECORDING_SNAPSHOT)
        assert vms["session"].track == "Spa-Francorchamps"
        assert vms["session"].currentLap == 7
        assert vms["session"].speedKph == pytest.approx(247.3)


# ---------------------------------------------------------------------------
# 3. Snapshot propagates to OverlayViewModel
# ---------------------------------------------------------------------------

class TestSnapshotPropagatesToOverlayVM:
    """Simulating a snapshot through to overlay_vm."""

    def test_overlay_vm_speed_updated(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["overlay"].update_from_snapshot(RECORDING_SNAPSHOT)
        assert vms["overlay"].speedKph == pytest.approx(247.3)

    def test_overlay_vm_throttle_updated(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["overlay"].update_from_snapshot(RECORDING_SNAPSHOT)
        assert vms["overlay"].throttlePct == pytest.approx(0.87)

    def test_overlay_vm_track_updated(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["overlay"].update_from_snapshot(RECORDING_SNAPSHOT)
        assert vms["overlay"].track == "Spa-Francorchamps"

    def test_overlay_vm_is_recording(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["overlay"].update_from_snapshot(RECORDING_SNAPSHOT)
        assert vms["overlay"].isRecording is True

    def test_overlay_vm_lap_number(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["overlay"].update_from_snapshot(RECORDING_SNAPSHOT)
        assert vms["overlay"].lapNumber == 7

    def test_snapshot_signal_propagates_to_overlay_vm(self) -> None:
        """Emit on the service signal -> overlay_vm gets updated automatically."""
        svc = _mock_service()
        vms = build_view_models(svc)
        svc.snapshot_changed.emit(RECORDING_SNAPSHOT)
        assert vms["overlay"].track == "Spa-Francorchamps"
        assert vms["overlay"].speedKph == pytest.approx(247.3)
        assert vms["overlay"].isRecording is True

    def test_snapshot_propagates_to_both_session_and_overlay(self) -> None:
        """A single snapshot_changed emit should update both VMs."""
        svc = _mock_service()
        vms = build_view_models(svc)
        svc.snapshot_changed.emit(RECORDING_SNAPSHOT)
        # Session VM
        assert vms["session"].track == "Spa-Francorchamps"
        assert vms["session"].currentLap == 7
        # Overlay VM
        assert vms["overlay"].track == "Spa-Francorchamps"
        assert vms["overlay"].lapNumber == 7


# ---------------------------------------------------------------------------
# 4. History update propagates
# ---------------------------------------------------------------------------

class TestHistoryUpdatePropagates:
    """history_vm.update_sessions should make sessions accessible."""

    def test_sessions_accessible_after_update(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["history"].update_sessions(SAMPLE_SESSIONS)
        assert len(vms["history"].sessions) == 3

    def test_sessions_count_matches(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["history"].update_sessions(SAMPLE_SESSIONS)
        assert vms["history"].count == 3

    def test_session_data_accessible_by_index(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["history"].update_sessions(SAMPLE_SESSIONS)
        assert vms["history"].sessions[0]["track"] == "Spa-Francorchamps"
        assert vms["history"].sessions[1]["sim"] == "ACC"
        assert vms["history"].sessions[2]["session_id"] == "int-003"

    def test_folder_at_works(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["history"].update_sessions(SAMPLE_SESSIONS)
        assert vms["history"].folderAt(0) == "/sessions/2026-04-01_spa"

    def test_session_id_at_works(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["history"].update_sessions(SAMPLE_SESSIONS)
        assert vms["history"].sessionIdAt(1) == "int-002"

    def test_history_signal_propagates(self) -> None:
        """Emit on the service signal -> history_vm updates automatically."""
        svc = _mock_service()
        vms = build_view_models(svc)
        svc.history_changed.emit(SAMPLE_SESSIONS)
        assert len(vms["history"].sessions) == 3
        assert vms["history"].count == 3


# ---------------------------------------------------------------------------
# 5. Review load propagates
# ---------------------------------------------------------------------------

class TestReviewLoadPropagates:
    """review_vm.load should make review data accessible."""

    def test_data_accessible_after_load(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["review"].load(SAMPLE_REVIEW)
        assert vms["review"].data == SAMPLE_REVIEW

    def test_path_set_from_folder(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["review"].load(SAMPLE_REVIEW)
        assert vms["review"].path == "/sessions/2026-04-01_spa"

    def test_section_defaults_to_overview(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["review"].load(SAMPLE_REVIEW)
        assert vms["review"].section == "overview"

    def test_section_navigation_works(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["review"].load(SAMPLE_REVIEW)
        vms["review"].setSection("laps")
        assert vms["review"].section == "laps"
        vms["review"].setSection("quality")
        assert vms["review"].section == "quality"

    def test_review_signal_propagates(self) -> None:
        """Emit on the service signal -> review_vm loads automatically."""
        svc = _mock_service()
        vms = build_view_models(svc)
        svc.review_changed.emit(SAMPLE_REVIEW)
        assert vms["review"].data == SAMPLE_REVIEW
        assert vms["review"].path == "/sessions/2026-04-01_spa"
        assert vms["review"].section == "overview"


# ---------------------------------------------------------------------------
# 6. Settings roundtrip
# ---------------------------------------------------------------------------

class TestSettingsRoundtrip:
    """Settings load -> modify -> save cycle."""

    def test_initial_settings_loaded(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        assert vms["settings"].values.get("output_dir") == "C:\\Users\\Test\\sessions"
        assert vms["settings"].values.get("driver_name") == "Test Driver"

    def test_get_string_works(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        assert vms["settings"].getString("driver_name") == "Test Driver"

    def test_get_float_works(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        assert vms["settings"].getFloat("sample_rate_hz") == 60.0

    def test_get_bool_works(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        assert vms["settings"].getBool("enable_iracing") is True
        assert vms["settings"].getBool("enable_lmu") is False

    def test_modify_value(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["settings"].setValue("driver_name", "New Driver")
        assert vms["settings"].getString("driver_name") == "New Driver"

    def test_save_emits_save_requested(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["settings"].setValue("driver_name", "New Driver")
        vms["settings"].save()
        assert vms["settings"].saveRequested.call_count == 1

    def test_save_emitted_dict_contains_modification(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        vms["settings"].setValue("driver_name", "New Driver")
        vms["settings"].save()
        emitted = vms["settings"].saveRequested.call_args[0][0]
        assert emitted["driver_name"] == "New Driver"

    def test_settings_saved_signal_reloads(self) -> None:
        """service.settings_saved -> settings_vm reloads from service snapshot."""
        svc = _mock_service()
        vms = build_view_models(svc)
        # Modify the value locally
        vms["settings"].setValue("driver_name", "Local Only")
        assert vms["settings"].getString("driver_name") == "Local Only"
        # Simulate the service acknowledging save with updated snapshot
        updated = dict(SETTINGS_SNAPSHOT)
        updated["driver_name"] = "Confirmed Driver"
        svc.settings_snapshot.return_value = updated
        svc.settings_saved.emit({})
        # The VM should now reflect the service's canonical state
        assert vms["settings"].getString("driver_name") == "Confirmed Driver"


# ---------------------------------------------------------------------------
# 7. Onboarding flow
# ---------------------------------------------------------------------------

class TestOnboardingFlow:
    """Step through all 3 steps, toggle sims, finish, verify completed."""

    def test_initial_state(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        ob = vms["onboarding"]
        assert ob.step == 0
        assert ob.totalSteps == 3
        assert ob.completed is False

    def test_step_through_all(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        ob = vms["onboarding"]
        ob.nextStep()
        assert ob.step == 1
        ob.nextStep()
        assert ob.step == 2
        # Cannot go past totalSteps - 1
        ob.nextStep()
        assert ob.step == 2

    def test_step_back(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        ob = vms["onboarding"]
        ob.nextStep()
        ob.nextStep()
        ob.prevStep()
        assert ob.step == 1

    def test_toggle_sims(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        ob = vms["onboarding"]
        # Default: iRacing=True, ACC=True, Assetto Corsa=False, LMU=False
        assert ob.sims["iRacing"] is True
        assert ob.sims["Assetto Corsa"] is False
        ob.toggleSim("Assetto Corsa")
        assert ob.sims["Assetto Corsa"] is True
        ob.toggleSim("iRacing")
        assert ob.sims["iRacing"] is False

    def test_finish_completes(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        ob = vms["onboarding"]
        ob.nextStep()
        ob.nextStep()
        ob.toggleSim("Assetto Corsa")
        ob.finish()
        assert ob.completed is True

    def test_completed_signal_fires(self) -> None:
        svc = _mock_service()
        vms = build_view_models(svc)
        ob = vms["onboarding"]
        ob.finish()
        assert ob.completedChanged.call_count == 1

    def test_full_wizard_flow(self) -> None:
        """End-to-end: step 0 -> 1 -> 2, toggle sims, finish."""
        svc = _mock_service()
        vms = build_view_models(svc)
        ob = vms["onboarding"]

        # Step 0: welcome
        assert ob.step == 0
        ob.nextStep()

        # Step 1: sim selection
        assert ob.step == 1
        ob.toggleSim("Le Mans Ultimate")  # enable
        assert ob.sims["Le Mans Ultimate"] is True
        ob.toggleSim("ACC")  # disable
        assert ob.sims["ACC"] is False
        ob.nextStep()

        # Step 2: confirmation
        assert ob.step == 2
        ob.finish()

        assert ob.completed is True
        assert ob.sims["Le Mans Ultimate"] is True
        assert ob.sims["ACC"] is False
        assert ob.sims["iRacing"] is True


# ---------------------------------------------------------------------------
# 8. All VM tests pass together (meta-test)
# ---------------------------------------------------------------------------

_VM_TEST_FILES = [
    "tests/test_service_vm.py",
    "tests/test_session_vm.py",
    "tests/test_history_vm.py",
    "tests/test_review_vm.py",
    "tests/test_settings_vm.py",
    "tests/test_overlay_vm.py",
    "tests/test_onboarding_vm.py",
    "tests/test_qml_bootstrap.py",
]


class TestAllVMTestsPassTogether:
    """Meta-test: run all individual VM test files in a single subprocess
    to verify no cross-contamination between module-level PySide6 mocks."""

    def test_all_vm_tests_pass_in_single_process(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", *_VM_TEST_FILES, "-q", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"VM tests failed with exit code {result.returncode}.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
