"""Tests for ReviewViewModel -- session review panel for QML."""

from __future__ import annotations

import pytest

from tests.qt_mock import install
install()

from lap_coach_logger.viewmodels.review_vm import ReviewViewModel  # noqa: E402


# ---------------------------------------------------------------------------
# Sample review data
# ---------------------------------------------------------------------------

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
# Default property values
# ---------------------------------------------------------------------------

class TestDefaultProperties:
    """Before any review is loaded, properties should have safe defaults."""

    def test_data_default_empty(self) -> None:
        vm = ReviewViewModel()
        assert vm.data == {}

    def test_section_default_empty(self) -> None:
        vm = ReviewViewModel()
        assert vm.section == ""

    def test_path_default_empty(self) -> None:
        vm = ReviewViewModel()
        assert vm.path == ""


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------

class TestLoad:
    """load() should populate data, path, and reset section to 'overview'."""

    def test_load_populates_data(self) -> None:
        vm = ReviewViewModel()
        vm.load(SAMPLE_REVIEW)
        assert vm.data == SAMPLE_REVIEW

    def test_load_sets_path_from_folder(self) -> None:
        vm = ReviewViewModel()
        vm.load(SAMPLE_REVIEW)
        assert vm.path == "/sessions/2026-04-01_spa"

    def test_load_resets_section_to_overview(self) -> None:
        vm = ReviewViewModel()
        vm.setSection("laps")
        vm.load(SAMPLE_REVIEW)
        assert vm.section == "overview"

    def test_load_emits_data_changed(self) -> None:
        vm = ReviewViewModel()
        vm.load(SAMPLE_REVIEW)
        assert vm.dataChanged.call_count == 1

    def test_load_emits_section_changed(self) -> None:
        vm = ReviewViewModel()
        vm.load(SAMPLE_REVIEW)
        assert vm.sectionChanged.call_count >= 1

    def test_load_missing_folder_defaults_to_empty_path(self) -> None:
        vm = ReviewViewModel()
        vm.load({"track": "Monza"})
        assert vm.path == ""


# ---------------------------------------------------------------------------
# setSection
# ---------------------------------------------------------------------------

class TestSetSection:
    """setSection should update section and emit sectionChanged."""

    def test_set_section_updates(self) -> None:
        vm = ReviewViewModel()
        vm.setSection("laps")
        assert vm.section == "laps"

    def test_set_section_emits_signal(self) -> None:
        vm = ReviewViewModel()
        vm.setSection("quality")
        assert vm.sectionChanged.call_count == 1

    def test_set_section_multiple_times(self) -> None:
        vm = ReviewViewModel()
        vm.setSection("laps")
        vm.setSection("quality")
        vm.setSection("overview")
        assert vm.section == "overview"
        assert vm.sectionChanged.call_count == 3


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------

class TestClear:
    """clear() should reset all state back to defaults."""

    def test_clear_resets_data(self) -> None:
        vm = ReviewViewModel()
        vm.load(SAMPLE_REVIEW)
        vm.clear()
        assert vm.data == {}

    def test_clear_resets_section(self) -> None:
        vm = ReviewViewModel()
        vm.load(SAMPLE_REVIEW)
        vm.setSection("laps")
        vm.clear()
        assert vm.section == ""

    def test_clear_resets_path(self) -> None:
        vm = ReviewViewModel()
        vm.load(SAMPLE_REVIEW)
        vm.clear()
        assert vm.path == ""

    def test_clear_emits_data_changed(self) -> None:
        vm = ReviewViewModel()
        vm.load(SAMPLE_REVIEW)
        pre = vm.dataChanged.call_count
        vm.clear()
        assert vm.dataChanged.call_count > pre

    def test_clear_emits_section_changed(self) -> None:
        vm = ReviewViewModel()
        vm.load(SAMPLE_REVIEW)
        pre = vm.sectionChanged.call_count
        vm.clear()
        assert vm.sectionChanged.call_count > pre
