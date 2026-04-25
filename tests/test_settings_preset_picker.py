"""T127: Preset picker in Settings.

Per spec — "Preset picker in Settings ⇒ works". The user opens
the Settings panel and picks one of the four built-in presets
(race-minimal / practice / endurance / streamer). The choice
persists via the existing ``settingsVM`` config bridge under
the ``"overlay_preset"`` key, ready for the overlay system to
read.

Two layers under test:

1. **SettingsViewModel.availablePresetOptions** — returns the
   list of (id, label) tuples QML uses to render the dropdown.
   Sourced from ``builtin_presets._BUILTIN_PRESETS`` so adding
   a future preset propagates without a separate edit here.

2. **SettingsPanel.qml** — contains a dropdown wired to
   ``settingsVM.setValue("overlay_preset", <id>)`` for each
   built-in preset. File-content regex (matching T116 / T094
   pattern, since QML rendering needs a QApplication).
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Python side: SettingsViewModel.availablePresetOptions
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtCore import QCoreApplication
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def test_settings_vm_exposes_available_preset_options(qapp) -> None:
    """The slot must exist + return a list. QML's Repeater
    consumes it directly to build the dropdown menu items."""
    from lap_coach_logger.viewmodels.settings_vm import SettingsViewModel

    vm = SettingsViewModel()

    options = vm.availablePresetOptions()

    assert isinstance(options, list)


def test_preset_options_include_all_four_built_in_presets(qapp) -> None:
    """Each of the four canonical presets (T122-T125) appears
    in the dropdown options. Sourced from the registry — adding
    a future preset will propagate here without extra work."""
    from lap_coach_logger.viewmodels.settings_vm import SettingsViewModel

    vm = SettingsViewModel()

    ids = [opt["id"] for opt in vm.availablePresetOptions()]

    assert set(ids) == {"race-minimal", "practice", "endurance", "streamer"}


def test_preset_options_each_carry_a_human_label(qapp) -> None:
    """Each option exposes a non-empty label so the dropdown
    can render readable items (not raw ids). Catches a refactor
    that surfaces the registry directly without title-casing
    the preset_id."""
    from lap_coach_logger.viewmodels.settings_vm import SettingsViewModel

    vm = SettingsViewModel()

    for opt in vm.availablePresetOptions():
        assert "label" in opt
        assert isinstance(opt["label"], str)
        assert opt["label"], f"empty label for preset {opt['id']!r}"


# ---------------------------------------------------------------------------
# QML side: SettingsPanel.qml has the picker wiring
# ---------------------------------------------------------------------------


_QML_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Panels" / "SettingsPanel.qml"
)


@pytest.fixture(scope="module")
def settings_qml() -> str:
    return _QML_PATH.read_text(encoding="utf-8")


def test_settings_panel_includes_preset_section_header(settings_qml: str) -> None:
    """A discoverable section header — drivers scrolling settings
    need a label to anchor on. ""OVERLAY PRESET"" matches the
    existing CAPS section style in this file."""
    assert "OVERLAY PRESET" in settings_qml


def test_settings_panel_wires_preset_picker_to_settings_vm(settings_qml: str) -> None:
    """The picker must persist via the existing key/value
    bridge. Pin the call shape (settingsVM.setValue with the
    ``"overlay_preset"`` key) so a refactor that switches to a
    different settings key gets caught."""
    assert 'settingsVM.setValue("overlay_preset"' in settings_qml


@pytest.mark.parametrize(
    "preset_id",
    ["race-minimal", "practice", "endurance", "streamer"],
)
def test_settings_panel_offers_each_preset_in_picker(
    settings_qml: str, preset_id: str
) -> None:
    """Each built-in preset must appear in the dropdown so users
    can pick any of them. Pinned individually so the failure
    message identifies *which* preset went missing."""
    assert preset_id in settings_qml, (
        f"SettingsPanel.qml must wire the {preset_id!r} preset into the picker"
    )
