"""Tests for ModeDescriptor registry."""
from __future__ import annotations

from lap_coach_logger.core.mode_descriptor import (
    COACHING,
    DATA,
    ENDURANCE,
    MODE_REGISTRY,
    SPRINT,
    get_mode,
)


def test_registry_has_four_modes():
    assert set(MODE_REGISTRY.keys()) == {"sprint", "endurance", "coaching", "data"}


def test_sprint_tabs():
    assert SPRINT.tab_ids() == ["setup", "live"]
    assert SPRINT.default_tab == "setup"


def test_endurance_tabs():
    assert ENDURANCE.tab_ids() == ["practice", "build", "raceplan"]
    assert ENDURANCE.auto_record_practice is True


def test_coaching_tabs():
    assert COACHING.tab_ids() == ["consistency", "pace", "readiness"]
    assert COACHING.alert_policy == "none"


def test_data_tabs():
    assert DATA.tab_ids() == ["telemetry", "export"]


def test_resolve_active_tab_sprint():
    assert SPRINT.resolve_active_tab(has_plan=False, has_profiles=False) == "setup"
    assert SPRINT.resolve_active_tab(has_plan=True, has_profiles=True) == "live"


def test_resolve_active_tab_endurance():
    assert ENDURANCE.resolve_active_tab(has_plan=False, has_profiles=False) == "practice"
    assert ENDURANCE.resolve_active_tab(has_plan=False, has_profiles=True) == "build"
    assert ENDURANCE.resolve_active_tab(has_plan=True, has_profiles=True) == "raceplan"


def test_get_mode_unknown_returns_sprint():
    assert get_mode("unknown").key == "sprint"
    assert get_mode("").key == "sprint"


def test_tab_dicts_format():
    dicts = SPRINT.tab_dicts()
    assert dicts[0] == {"id": "setup", "label": "SETUP"}


def test_has_tab():
    assert SPRINT.has_tab("setup") is True
    assert SPRINT.has_tab("practice") is False


def test_overlay_profiles_are_frozensets():
    for mode in MODE_REGISTRY.values():
        assert isinstance(mode.overlay_profile, frozenset)


def test_all_modes_have_sync_tags():
    for mode in MODE_REGISTRY.values():
        assert len(mode.sync_tags) > 0
