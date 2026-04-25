"""T117: Mode selection persists across app restarts.

The user picks a mode (Sprint / Endurance / Coaching / Data) via
the T116 dropdown; that selection has to *survive* a quit-and-
relaunch so they don't drop back to ``"sprint"`` every cold
start. Pattern mirrors :class:`AccountRegistry` (T053): a tiny
file-backed JSON store under ``config_dir()`` plus a kwarg the
ViewModel accepts at construction time.

Two-instance simulation pins the round-trip: VM #1 calls
``setMode("endurance")``; we throw it away; VM #2 reads the same
state file and reports ``activeMode == "endurance"``. That's
the "app restart" flow — the OS process boundary doesn't matter
to the test, only the persistence boundary does.

Corrupt / missing state files are treated as cold start (return
the hard-coded default). Same defensive shape as ``AccountRegistry``:
losing the prefs file is a UX hiccup, not a crash, and the mode
falls back to the safest default ("sprint" — what the legacy
hardcoded init used).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# pytest-qt's qapp fixture is implicit, but ModeViewModel doesn't
# actually need a QApplication for setMode() / activeMode in this
# layer of test. Skip it.


# ---------------------------------------------------------------------------
# ModePreferenceStore: file-backed JSON
# ---------------------------------------------------------------------------


def test_fresh_store_returns_none_when_no_file_exists(tmp_path: Path) -> None:
    """Cold start: no state file ⇒ no persisted mode. Caller
    falls back to the default."""
    from lap_coach_logger.mode_preference import ModePreferenceStore

    store = ModePreferenceStore(state_path=tmp_path / "mode.json")

    assert store.load() is None


def test_save_then_load_round_trips_the_mode(tmp_path: Path) -> None:
    from lap_coach_logger.mode_preference import ModePreferenceStore

    path = tmp_path / "mode.json"
    ModePreferenceStore(state_path=path).save("endurance")

    assert ModePreferenceStore(state_path=path).load() == "endurance"


def test_corrupt_json_is_treated_as_cold_start(tmp_path: Path) -> None:
    """If the state file is half-written or hand-edited into
    invalid JSON, ``load()`` must return ``None`` rather than
    raise — the caller will fall back to the default mode and
    the next ``save()`` will rewrite a valid file."""
    from lap_coach_logger.mode_preference import ModePreferenceStore

    path = tmp_path / "mode.json"
    path.write_text("{not valid json", encoding="utf-8")

    assert ModePreferenceStore(state_path=path).load() is None


def test_payload_with_unexpected_shape_is_treated_as_cold_start(
    tmp_path: Path,
) -> None:
    """Hand-edited payload with no ``mode`` key (or wrong type)
    is non-fatal — same defensive shape as ``AccountRegistry``."""
    from lap_coach_logger.mode_preference import ModePreferenceStore

    path = tmp_path / "mode.json"
    path.write_text(json.dumps({"unrelated": "value"}), encoding="utf-8")

    assert ModePreferenceStore(state_path=path).load() is None


# ---------------------------------------------------------------------------
# ModeViewModel integration: load on init, save on setMode
# ---------------------------------------------------------------------------


def test_vm_without_preference_store_keeps_legacy_default(qapp) -> None:
    """Pre-T117 callers don't pass a store. activeMode stays
    ``"sprint"`` so existing tests + production code keep working
    unchanged."""
    from lap_coach_logger.viewmodels.mode_vm import ModeViewModel

    vm = ModeViewModel()

    assert vm.activeMode == "sprint"


def test_vm_loads_persisted_mode_at_construction_time(
    qapp, tmp_path: Path
) -> None:
    """The 'app restart' path: a previous session saved
    'endurance'; this fresh VM picks it up at construction
    time so the user lands in their preferred mode immediately,
    not after the first manual switch."""
    from lap_coach_logger.mode_preference import ModePreferenceStore
    from lap_coach_logger.viewmodels.mode_vm import ModeViewModel

    store = ModePreferenceStore(state_path=tmp_path / "mode.json")
    store.save("endurance")

    vm = ModeViewModel(preference_store=store)

    assert vm.activeMode == "endurance"


def test_vm_persists_to_store_on_setMode_transition(  # noqa: N802
    qapp, tmp_path: Path
) -> None:
    """Two-VM round-trip: VM #1 calls setMode('coaching'); we
    discard it; VM #2 with the same store reports 'coaching'.
    That's the persistence contract — process boundary doesn't
    have to be real to test it, just the file boundary."""
    from lap_coach_logger.mode_preference import ModePreferenceStore
    from lap_coach_logger.viewmodels.mode_vm import ModeViewModel

    path = tmp_path / "mode.json"

    vm1 = ModeViewModel(preference_store=ModePreferenceStore(state_path=path))
    vm1.setMode("coaching")

    vm2 = ModeViewModel(preference_store=ModePreferenceStore(state_path=path))

    assert vm2.activeMode == "coaching"


def test_vm_does_not_persist_invalid_mode_strings(
    qapp, tmp_path: Path
) -> None:
    """``setMode("garbage")`` is already a no-op in ModeViewModel
    (doesn't change ``_active_mode``). It must also not write to
    the prefs file — otherwise a typo'd mode could poison the
    persisted state and break the next launch."""
    from lap_coach_logger.mode_preference import ModePreferenceStore
    from lap_coach_logger.viewmodels.mode_vm import ModeViewModel

    path = tmp_path / "mode.json"
    store = ModePreferenceStore(state_path=path)

    vm = ModeViewModel(preference_store=store)
    vm.setMode("not-a-mode")

    # No file written ⇒ a fresh VM still cold-starts to default.
    fresh = ModeViewModel(preference_store=ModePreferenceStore(state_path=path))
    assert fresh.activeMode == "sprint"


@pytest.fixture(scope="module")
def qapp():
    """Minimal QApplication so ModeViewModel (a QObject) can be
    constructed without 'No QCoreApplication' warnings."""
    from PySide6.QtCore import QCoreApplication
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app
