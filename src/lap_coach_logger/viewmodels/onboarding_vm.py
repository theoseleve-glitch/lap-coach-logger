"""OnboardingViewModel -- first-run wizard bridge for QML.

Manages step navigation and simulator selection for the onboarding
wizard that runs on first launch.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Property, QObject, Signal, Slot

log = logging.getLogger(__name__)

_DEFAULT_SIMS: dict[str, bool] = {
    "iRacing": True,
    "ACC": True,
    "Assetto Corsa": False,
    "Le Mans Ultimate": False,
}

_TOTAL_STEPS: int = 3


class OnboardingViewModel(QObject):
    """Exposes onboarding wizard state as flat, QML-bindable properties."""

    # -- change signals --------------------------------------------------------
    stepChanged = Signal()
    simsChanged = Signal()
    completedChanged = Signal()

    # -- construction ----------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()

        self._step: int = 0
        self._sims: dict[str, bool] = dict(_DEFAULT_SIMS)
        self._completed: bool = False

    # -- QML properties --------------------------------------------------------

    @Property(int, notify=stepChanged)
    def step(self) -> int:
        """Current wizard step (0-based)."""
        return self._step

    @Property(int, constant=True)
    def totalSteps(self) -> int:  # noqa: N802
        """Total number of wizard steps (constant)."""
        return _TOTAL_STEPS

    @Property("QVariant", notify=simsChanged)
    def sims(self) -> dict[str, bool]:
        """Simulator selection map: name -> enabled."""
        return self._sims

    @Property(bool, notify=completedChanged)
    def completed(self) -> bool:
        """Whether the wizard has been completed."""
        return self._completed

    # -- slots (QML callable) --------------------------------------------------

    @Slot()
    def nextStep(self) -> None:  # noqa: N802
        """Advance to the next step, capped at ``totalSteps - 1``."""
        new_step = min(self._step + 1, _TOTAL_STEPS - 1)
        if new_step != self._step:
            self._step = new_step
            self.stepChanged.emit()

    @Slot()
    def prevStep(self) -> None:  # noqa: N802
        """Go back to the previous step, capped at 0."""
        new_step = max(self._step - 1, 0)
        if new_step != self._step:
            self._step = new_step
            self.stepChanged.emit()

    @Slot(str)
    def toggleSim(self, sim: str) -> None:  # noqa: N802
        """Toggle the enabled state of a simulator."""
        self._sims[sim] = not self._sims.get(sim, False)
        self.simsChanged.emit()

    @Slot()
    def finish(self) -> None:
        """Mark the onboarding wizard as completed."""
        self._completed = True
        self.completedChanged.emit()
