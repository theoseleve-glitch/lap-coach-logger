"""Tests for HistoryViewModel -- filterable session list for QML."""

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
    """Per-object signal instance that records emit() calls."""

    def __init__(self) -> None:
        self._mock = MagicMock()

    def emit(self, *args: object) -> None:
        self._mock(*args)

    def connect(self, slot: object) -> None:  # noqa: ARG002
        pass

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

from lap_coach_logger.viewmodels.history_vm import HistoryViewModel  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_SESSIONS: list[dict] = [
    {
        "session_id": "sess-001",
        "folder": "/sessions/2026-04-01_spa",
        "track": "Spa-Francorchamps",
        "car": "BMW M4 GT3",
        "sim": "iRacing",
    },
    {
        "session_id": "sess-002",
        "folder": "/sessions/2026-04-02_monza",
        "track": "Monza",
        "car": "Ferrari 296 GT3",
        "sim": "ACC",
    },
    {
        "session_id": "sess-003",
        "folder": "/sessions/2026-04-03_nords",
        "track": "Nordschleife",
        "car": "Porsche 911 GT3 R",
        "sim": "iRacing",
    },
    {
        "session_id": "sess-004",
        "folder": "/sessions/2026-04-04_suzuka",
        "track": "Suzuka",
        "car": "McLaren 720S GT3",
        "sim": "ACC",
    },
]


# ---------------------------------------------------------------------------
# Default property values
# ---------------------------------------------------------------------------

class TestDefaultProperties:
    """Before any sessions are loaded, properties should have safe defaults."""

    def test_sessions_default_empty(self) -> None:
        vm = HistoryViewModel()
        assert vm.sessions == []

    def test_count_default_zero(self) -> None:
        vm = HistoryViewModel()
        assert vm.count == 0

    def test_search_text_default_empty(self) -> None:
        vm = HistoryViewModel()
        assert vm.searchText == ""

    def test_sim_filter_default_empty(self) -> None:
        vm = HistoryViewModel()
        assert vm.simFilter == ""


# ---------------------------------------------------------------------------
# update_sessions
# ---------------------------------------------------------------------------

class TestUpdateSessions:
    """update_sessions should populate the list and emit signals."""

    def test_populates_sessions(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        assert len(vm.sessions) == 4

    def test_count_reflects_total_unfiltered(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        assert vm.count == 4

    def test_emits_sessions_changed(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        assert vm.sessionsChanged.call_count == 1

    def test_replaces_previous_sessions(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS[:2])
        assert vm.count == 2
        vm.update_sessions(SAMPLE_SESSIONS)
        assert vm.count == 4


# ---------------------------------------------------------------------------
# Search filter
# ---------------------------------------------------------------------------

class TestSearchFilter:
    """Search text should filter sessions by track, sim, or car (case-insensitive)."""

    def test_search_by_track_case_insensitive(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSearchText("spa")
        assert len(vm.sessions) == 1
        assert vm.sessions[0]["track"] == "Spa-Francorchamps"

    def test_search_by_sim(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSearchText("iracing")
        assert len(vm.sessions) == 2
        assert all(s["sim"] == "iRacing" for s in vm.sessions)

    def test_search_by_car(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSearchText("ferrari")
        assert len(vm.sessions) == 1
        assert vm.sessions[0]["car"] == "Ferrari 296 GT3"

    def test_search_strips_whitespace(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSearchText("  spa  ")
        assert len(vm.sessions) == 1

    def test_empty_search_returns_all(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSearchText("spa")
        assert len(vm.sessions) == 1
        vm.setSearchText("")
        assert len(vm.sessions) == 4

    def test_search_emits_search_text_changed(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSearchText("monza")
        assert vm.searchTextChanged.call_count == 1

    def test_search_emits_sessions_changed(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        pre = vm.sessionsChanged.call_count
        vm.setSearchText("monza")
        assert vm.sessionsChanged.call_count > pre

    def test_search_no_match_returns_empty(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSearchText("laguna seca")
        assert len(vm.sessions) == 0

    def test_count_stays_total_unfiltered_during_search(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSearchText("spa")
        assert vm.count == 4  # total, not filtered


# ---------------------------------------------------------------------------
# Sim filter
# ---------------------------------------------------------------------------

class TestSimFilter:
    """Sim filter should exact-match on sim name."""

    def test_sim_filter_exact_match(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSimFilter("ACC")
        assert len(vm.sessions) == 2
        assert all(s["sim"] == "ACC" for s in vm.sessions)

    def test_sim_filter_empty_returns_all(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSimFilter("ACC")
        assert len(vm.sessions) == 2
        vm.setSimFilter("")
        assert len(vm.sessions) == 4

    def test_sim_filter_emits_sim_filter_changed(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSimFilter("iRacing")
        assert vm.simFilterChanged.call_count == 1

    def test_sim_filter_emits_sessions_changed(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        pre = vm.sessionsChanged.call_count
        vm.setSimFilter("iRacing")
        assert vm.sessionsChanged.call_count > pre

    def test_sim_filter_no_match_returns_empty(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSimFilter("rFactor")
        assert len(vm.sessions) == 0


# ---------------------------------------------------------------------------
# Combined search + sim filter
# ---------------------------------------------------------------------------

class TestCombinedFilters:
    """Search and sim filter should combine with AND logic."""

    def test_search_and_sim_filter_combined(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSimFilter("iRacing")
        vm.setSearchText("spa")
        assert len(vm.sessions) == 1
        assert vm.sessions[0]["track"] == "Spa-Francorchamps"

    def test_combined_no_match(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSimFilter("ACC")
        vm.setSearchText("spa")
        # Spa is iRacing, not ACC
        assert len(vm.sessions) == 0

    def test_clear_sim_filter_restores_search_only(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSearchText("gt3")
        vm.setSimFilter("iRacing")
        # GT3 appears in all cars; iRacing has 2 sessions
        iracing_gt3 = len(vm.sessions)
        vm.setSimFilter("")
        # Now just search for gt3 across all sims
        assert len(vm.sessions) > iracing_gt3


# ---------------------------------------------------------------------------
# folderAt / sessionIdAt
# ---------------------------------------------------------------------------

class TestIndexAccessors:
    """folderAt and sessionIdAt should return values at valid indices."""

    def test_folder_at_valid_index(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        assert vm.folderAt(0) == "/sessions/2026-04-01_spa"
        assert vm.folderAt(1) == "/sessions/2026-04-02_monza"

    def test_session_id_at_valid_index(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        assert vm.sessionIdAt(0) == "sess-001"
        assert vm.sessionIdAt(3) == "sess-004"

    def test_folder_at_invalid_index_returns_empty(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        assert vm.folderAt(-1) == ""
        assert vm.folderAt(99) == ""

    def test_session_id_at_invalid_index_returns_empty(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        assert vm.sessionIdAt(-1) == ""
        assert vm.sessionIdAt(99) == ""

    def test_folder_at_empty_list(self) -> None:
        vm = HistoryViewModel()
        assert vm.folderAt(0) == ""

    def test_session_id_at_empty_list(self) -> None:
        vm = HistoryViewModel()
        assert vm.sessionIdAt(0) == ""

    def test_folder_at_respects_filter(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSimFilter("ACC")
        # Filtered list: Monza (ACC), Suzuka (ACC)
        assert vm.folderAt(0) == "/sessions/2026-04-02_monza"
        assert vm.sessionIdAt(0) == "sess-002"

    def test_session_id_at_respects_filter(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSimFilter("ACC")
        assert vm.sessionIdAt(1) == "sess-004"


# ---------------------------------------------------------------------------
# update_sessions re-applies active filters
# ---------------------------------------------------------------------------

class TestUpdateReappliesFilters:
    """When update_sessions is called, active filters should be re-applied."""

    def test_search_reapplied_on_update(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSearchText("spa")
        assert len(vm.sessions) == 1
        # Update with new data that also has Spa
        new_sessions = SAMPLE_SESSIONS + [{
            "session_id": "sess-005",
            "folder": "/sessions/2026-04-05_spa2",
            "track": "Spa-Francorchamps",
            "car": "Audi R8 LMS",
            "sim": "ACC",
        }]
        vm.update_sessions(new_sessions)
        assert len(vm.sessions) == 2

    def test_sim_filter_reapplied_on_update(self) -> None:
        vm = HistoryViewModel()
        vm.update_sessions(SAMPLE_SESSIONS)
        vm.setSimFilter("ACC")
        assert len(vm.sessions) == 2
        # Update with only iRacing sessions
        iracing_only = [s for s in SAMPLE_SESSIONS if s["sim"] == "iRacing"]
        vm.update_sessions(iracing_only)
        assert len(vm.sessions) == 0
