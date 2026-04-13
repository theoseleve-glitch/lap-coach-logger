"""Tests for ModeViewModel -- mode state management."""
from __future__ import annotations

from tests.qt_mock import install
install()

from lap_coach_logger.viewmodels.mode_vm import ModeViewModel  # noqa: E402


class TestDefaultState:

    def test_default_mode_is_sprint(self) -> None:
        vm = ModeViewModel()
        assert vm.activeMode == "sprint"


class TestSetMode:

    def test_set_mode(self) -> None:
        vm = ModeViewModel()
        vm.setMode("endurance")
        assert vm.activeMode == "endurance"

    def test_invalid_mode_rejected(self) -> None:
        vm = ModeViewModel()
        vm.setMode("turbo")
        assert vm.activeMode == "sprint"


class TestOnSessionDetected:

    def test_on_session_detected_sets_suggested_mode(self) -> None:
        vm = ModeViewModel()
        vm.onSessionDetected("practice", 0.0, False)
        assert vm.activeMode == "coaching"
        assert vm.bannerVisible is True

    def test_dismiss_banner(self) -> None:
        vm = ModeViewModel()
        vm.onSessionDetected("practice", 0.0, False)
        vm.dismissBanner()
        assert vm.bannerVisible is False

    def test_session_info(self) -> None:
        vm = ModeViewModel()
        vm.onSessionDetected("race", 1200.0, False)
        assert vm.activeMode == "sprint"
        assert vm.sessionType == "race"
