"""T111: ``ModeEngine`` — runtime mode selection + transitions.

Holds the registry of available modes (T107-T110), tracks the
current mode, and dispatches transitions. T112 / T113 / T114
register observer callbacks to react to mode changes
(overlay swap, coaching cadence, strategy assumptions). T117
persists the current mode across restarts.
"""
from __future__ import annotations

from typing import Callable

from lap_coach_logger.core.modes.base import Mode
from lap_coach_logger.core.modes.endurance import EnduranceMode
from lap_coach_logger.core.modes.practice import PracticeMode
from lap_coach_logger.core.modes.review import ReviewMode
from lap_coach_logger.core.modes.sprint import SprintMode


class UnknownModeError(KeyError):
    """Raised when a caller asks for a mode id the engine
    doesn't have registered. KeyError-derived so existing
    ``except KeyError`` paths still trip; the typed subclass
    lets new code pattern-match precisely."""


_BUILTIN_MODE_CLASSES: tuple[type[Mode], ...] = (
    PracticeMode,
    SprintMode,
    EnduranceMode,
    ReviewMode,
)


class ModeEngine:
    """Owns the current mode and notifies observers on change."""

    def __init__(self, *, default_mode_id: str = "practice") -> None:
        self._modes: dict[str, Mode] = {
            cls.id: cls() for cls in _BUILTIN_MODE_CLASSES
        }
        if default_mode_id not in self._modes:
            raise UnknownModeError(
                f"unknown mode id: {default_mode_id!r}; "
                f"known: {sorted(self._modes)}"
            )
        self._current: Mode = self._modes[default_mode_id]
        self._observers: list[Callable[[Mode], None]] = []

    @property
    def available_modes(self) -> list[Mode]:
        """Snapshot list of every registered mode. T116's
        toolbar dropdown reads this to populate its menu."""
        return list(self._modes.values())

    @property
    def current(self) -> Mode:
        """The currently active mode."""
        return self._current

    def get_mode(self, mode_id: str) -> Mode:
        """Look up a mode without switching. Useful for menu
        rendering — caller wants each mode's display name
        without changing the engine state."""
        try:
            return self._modes[mode_id]
        except KeyError:
            raise UnknownModeError(
                f"unknown mode id: {mode_id!r}; "
                f"known: {sorted(self._modes)}"
            ) from None

    def set_mode(self, mode_id: str) -> Mode:
        """Switch to ``mode_id``. Idempotent (re-setting to the
        current mode does NOT fire observers). Returns the
        mode instance for chaining."""
        target = self.get_mode(mode_id)
        if target is self._current:
            return target
        self._current = target
        for observer in self._observers:
            observer(target)
        return target

    def on_mode_changed(
        self, callback: Callable[[Mode], None]
    ) -> None:
        """Register a callback for mode-change notifications.
        Called in registration order on every successful
        ``set_mode`` that actually changes the current mode."""
        self._observers.append(callback)


__all__ = ["ModeEngine", "UnknownModeError"]
