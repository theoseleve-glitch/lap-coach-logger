"""Tests for OnboardingViewModel -- first-run wizard for QML."""

from __future__ import annotations

import pytest

from tests.qt_mock import install
install()

from lap_coach_logger.viewmodels.onboarding_vm import OnboardingViewModel  # noqa: E402


# ---------------------------------------------------------------------------
# Default property values
# ---------------------------------------------------------------------------

class TestDefaultProperties:
    """Before any interaction, properties should have safe defaults."""

    def test_step_default(self) -> None:
        vm = OnboardingViewModel()
        assert vm.step == 0

    def test_total_steps_default(self) -> None:
        vm = OnboardingViewModel()
        assert vm.totalSteps == 3

    def test_sims_default(self) -> None:
        vm = OnboardingViewModel()
        expected = {
            "iRacing": True,
            "ACC": True,
            "Assetto Corsa": False,
            "Le Mans Ultimate": False,
        }
        assert vm.sims == expected

    def test_completed_default(self) -> None:
        vm = OnboardingViewModel()
        assert vm.completed is False


# ---------------------------------------------------------------------------
# Step progression
# ---------------------------------------------------------------------------

class TestStepProgression:
    """nextStep and prevStep should navigate within bounds."""

    def test_next_step_increments(self) -> None:
        vm = OnboardingViewModel()
        vm.nextStep()
        assert vm.step == 1

    def test_next_step_emits_step_changed(self) -> None:
        vm = OnboardingViewModel()
        vm.nextStep()
        assert vm.stepChanged.call_count == 1

    def test_next_step_multiple(self) -> None:
        vm = OnboardingViewModel()
        vm.nextStep()
        vm.nextStep()
        assert vm.step == 2

    def test_next_step_caps_at_total_minus_one(self) -> None:
        vm = OnboardingViewModel()
        for _ in range(10):
            vm.nextStep()
        assert vm.step == vm.totalSteps - 1

    def test_prev_step_decrements(self) -> None:
        vm = OnboardingViewModel()
        vm.nextStep()
        vm.nextStep()
        vm.prevStep()
        assert vm.step == 1

    def test_prev_step_emits_step_changed(self) -> None:
        vm = OnboardingViewModel()
        vm.nextStep()
        pre = vm.stepChanged.call_count
        vm.prevStep()
        assert vm.stepChanged.call_count > pre

    def test_prev_step_caps_at_zero(self) -> None:
        vm = OnboardingViewModel()
        vm.prevStep()
        assert vm.step == 0

    def test_prev_step_multiple_at_zero(self) -> None:
        vm = OnboardingViewModel()
        for _ in range(5):
            vm.prevStep()
        assert vm.step == 0


# ---------------------------------------------------------------------------
# Sim toggle
# ---------------------------------------------------------------------------

class TestSimToggle:
    """toggleSim should flip the enabled state of a simulator."""

    def test_toggle_enables_disabled_sim(self) -> None:
        vm = OnboardingViewModel()
        assert vm.sims["Assetto Corsa"] is False
        vm.toggleSim("Assetto Corsa")
        assert vm.sims["Assetto Corsa"] is True

    def test_toggle_disables_enabled_sim(self) -> None:
        vm = OnboardingViewModel()
        assert vm.sims["iRacing"] is True
        vm.toggleSim("iRacing")
        assert vm.sims["iRacing"] is False

    def test_toggle_emits_sims_changed(self) -> None:
        vm = OnboardingViewModel()
        vm.toggleSim("ACC")
        assert vm.simsChanged.call_count == 1

    def test_toggle_unknown_sim_adds_it(self) -> None:
        vm = OnboardingViewModel()
        vm.toggleSim("rFactor 2")
        assert vm.sims["rFactor 2"] is True

    def test_toggle_twice_restores_original(self) -> None:
        vm = OnboardingViewModel()
        vm.toggleSim("iRacing")
        vm.toggleSim("iRacing")
        assert vm.sims["iRacing"] is True


# ---------------------------------------------------------------------------
# finish()
# ---------------------------------------------------------------------------

class TestFinish:
    """finish() should set completed to True and emit completedChanged."""

    def test_finish_sets_completed(self) -> None:
        vm = OnboardingViewModel()
        vm.finish()
        assert vm.completed is True

    def test_finish_emits_completed_changed(self) -> None:
        vm = OnboardingViewModel()
        vm.finish()
        assert vm.completedChanged.call_count == 1

    def test_finish_idempotent(self) -> None:
        vm = OnboardingViewModel()
        vm.finish()
        vm.finish()
        assert vm.completed is True
