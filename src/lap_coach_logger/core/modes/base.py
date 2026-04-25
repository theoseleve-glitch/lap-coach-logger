"""T106: ``Mode`` ABC — contract every mode subclass satisfies.

Per Q96, modes bind four orthogonal session-behaviour dimensions.
Subclasses (T107 PracticeMode, T108 SprintMode, T109
EnduranceMode, T110 ReviewMode) declare class-level constants —
modes are stateless and shareable, so no instance state is
needed.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal


CoachingVerbosity = Literal["off", "minimal", "verbose"]


class Mode(ABC):
    """Abstract base for runtime mode subclasses.

    Subclass pattern (mirrors T107-T110):

    .. code-block:: python

        class PracticeMode(Mode):
            id = "practice"
            name = "Practice"
            coaching_verbosity = "verbose"
            overlay_preset_id = "practice"
            environment_tag = "sim_practice"
            strategy_safety_margin = 0.0

    All six members are abstract — Python's ABC machinery will
    refuse instantiation if any are missing.
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """Stable string for serialization (settings persistence,
        T117). Mode subclasses use the lower-snake-case form
        of their conceptual name."""

    @property
    @abstractmethod
    def name(self) -> str:
        """User-facing label for the toolbar dropdown (T116)."""

    @property
    @abstractmethod
    def coaching_verbosity(self) -> CoachingVerbosity:
        """Drives T113's coaching cadence — ``"off"`` (no live
        coaching), ``"minimal"`` (race / endurance: don't
        distract), or ``"verbose"`` (practice: tell me
        everything)."""

    @property
    @abstractmethod
    def overlay_preset_id(self) -> str:
        """Which preset (T121-T125) the mode binds. T112
        switches the overlay stack on mode change."""

    @property
    @abstractmethod
    def environment_tag(self) -> str:
        """Stamped on finalize bundles (T115) so the server can
        aggregate sessions by mode (e.g., ``"sim_practice"``,
        ``"sim_sprint"``, ``"sim_endurance"``, ``"sim_review"``)."""

    @property
    @abstractmethod
    def strategy_safety_margin(self) -> float:
        """T114 scalar applied to fuel / time predictions — 0.0
        for tight Sprint racing, larger fractions for Endurance
        risk-averse stints."""


__all__ = ["CoachingVerbosity", "Mode"]
