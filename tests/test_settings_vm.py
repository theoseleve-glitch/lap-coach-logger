"""Tests for SettingsViewModel -- config read/write for QML."""

from __future__ import annotations

import pytest

from tests.qt_mock import install
install()

from lap_coach_logger.viewmodels.settings_vm import SettingsViewModel  # noqa: E402


# ---------------------------------------------------------------------------
# Sample config values
# ---------------------------------------------------------------------------

SAMPLE_CONFIG: dict = {
    "output_dir": "/home/user/sessions",
    "poll_hz": 60.0,
    "auto_start": True,
    "sync_enabled": False,
    "api_url": "https://lapcoach.example.com",
    "min_speed_kph": 5.0,
}


# ---------------------------------------------------------------------------
# Default property values
# ---------------------------------------------------------------------------

class TestDefaultProperties:
    """Before any config is loaded, properties should have safe defaults."""

    def test_values_default_empty(self) -> None:
        vm = SettingsViewModel()
        assert vm.values == {}

    def test_is_first_run_default_false(self) -> None:
        vm = SettingsViewModel()
        assert vm.isFirstRun is False


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------

class TestLoad:
    """load() should populate values and emit valuesChanged."""

    def test_load_populates_values(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        assert vm.values == SAMPLE_CONFIG

    def test_load_emits_values_changed(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        assert vm.valuesChanged.call_count == 1

    def test_load_replaces_previous_values(self) -> None:
        vm = SettingsViewModel()
        vm.load({"key_a": "old"})
        vm.load(SAMPLE_CONFIG)
        assert vm.values == SAMPLE_CONFIG

    def test_load_makes_internal_copy(self) -> None:
        vm = SettingsViewModel()
        source = {"key": "value"}
        vm.load(source)
        source["key"] = "mutated"
        assert vm.values["key"] == "value"


# ---------------------------------------------------------------------------
# getString / getFloat / getBool
# ---------------------------------------------------------------------------

class TestGetString:
    """getString should return str values or '' for missing keys."""

    def test_get_string_existing_key(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        assert vm.getString("output_dir") == "/home/user/sessions"

    def test_get_string_missing_key_returns_empty(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        assert vm.getString("nonexistent") == ""

    def test_get_string_coerces_non_string(self) -> None:
        vm = SettingsViewModel()
        vm.load({"count": 42})
        assert vm.getString("count") == "42"


class TestGetFloat:
    """getFloat should return float values or 0.0 for missing keys."""

    def test_get_float_existing_key(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        assert vm.getFloat("poll_hz") == 60.0

    def test_get_float_missing_key_returns_zero(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        assert vm.getFloat("nonexistent") == 0.0

    def test_get_float_coerces_int(self) -> None:
        vm = SettingsViewModel()
        vm.load({"count": 42})
        result = vm.getFloat("count")
        assert result == 42.0
        assert isinstance(result, float)

    def test_get_float_invalid_returns_zero(self) -> None:
        vm = SettingsViewModel()
        vm.load({"bad": "not_a_number"})
        assert vm.getFloat("bad") == 0.0


class TestGetBool:
    """getBool should return bool values or False for missing keys."""

    def test_get_bool_true_value(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        assert vm.getBool("auto_start") is True

    def test_get_bool_false_value(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        assert vm.getBool("sync_enabled") is False

    def test_get_bool_missing_key_returns_false(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        assert vm.getBool("nonexistent") is False

    def test_get_bool_truthy_value(self) -> None:
        vm = SettingsViewModel()
        vm.load({"truthy": 1})
        assert vm.getBool("truthy") is True

    def test_get_bool_falsy_value(self) -> None:
        vm = SettingsViewModel()
        vm.load({"falsy": 0})
        assert vm.getBool("falsy") is False


# ---------------------------------------------------------------------------
# setValue
# ---------------------------------------------------------------------------

class TestSetValue:
    """setValue should update the internal dict and emit valuesChanged."""

    def test_set_value_updates_dict(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        vm.setValue("output_dir", "/new/path")
        assert vm.getString("output_dir") == "/new/path"

    def test_set_value_emits_values_changed(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        pre = vm.valuesChanged.call_count
        vm.setValue("output_dir", "/new/path")
        assert vm.valuesChanged.call_count == pre + 1

    def test_set_value_adds_new_key(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        vm.setValue("new_key", "new_value")
        assert vm.getString("new_key") == "new_value"

    def test_set_value_on_empty_values(self) -> None:
        vm = SettingsViewModel()
        vm.setValue("key", "value")
        assert vm.getString("key") == "value"


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------

class TestSave:
    """save() should emit saveRequested with a copy of current values."""

    def test_save_emits_save_requested(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        vm.save()
        assert vm.saveRequested.call_count == 1

    def test_save_emits_copy_of_values(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        vm.save()
        emitted = vm.saveRequested.call_args[0][0]
        assert emitted == SAMPLE_CONFIG

    def test_save_emits_independent_copy(self) -> None:
        vm = SettingsViewModel()
        vm.load(SAMPLE_CONFIG)
        vm.save()
        emitted = vm.saveRequested.call_args[0][0]
        emitted["output_dir"] = "MUTATED"
        assert vm.getString("output_dir") == "/home/user/sessions"


# ---------------------------------------------------------------------------
# isFirstRun getter/setter
# ---------------------------------------------------------------------------

class TestIsFirstRun:
    """isFirstRun should be a readable/writable property with a change signal."""

    def test_set_is_first_run_true(self) -> None:
        vm = SettingsViewModel()
        vm.isFirstRun = True
        assert vm.isFirstRun is True

    def test_set_is_first_run_emits_signal(self) -> None:
        vm = SettingsViewModel()
        vm.isFirstRun = True
        assert vm.isFirstRunChanged.call_count == 1

    def test_set_is_first_run_false(self) -> None:
        vm = SettingsViewModel()
        vm.isFirstRun = True
        vm.isFirstRun = False
        assert vm.isFirstRun is False

    def test_set_is_first_run_no_emit_if_unchanged(self) -> None:
        vm = SettingsViewModel()
        # Default is False; setting to False should not emit
        vm.isFirstRun = False
        assert vm.isFirstRunChanged.call_count == 0
