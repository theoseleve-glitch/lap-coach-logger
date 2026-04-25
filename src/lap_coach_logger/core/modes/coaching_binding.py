"""T113: Mode → coaching verbosity binding.

Thin adapter that forwards each new :class:`Mode`'s
``coaching_verbosity`` to a target via ``target.set_verbosity(level)``.
Mirrors T112's overlay binding shape.
"""
from __future__ import annotations

from typing import Protocol

from lap_coach_logger.core.modes.engine import ModeEngine


class _VerbosityTarget(Protocol):
    """Structural shape of any object the binding can drive —
    just needs ``set_verbosity(level: str) -> None``. Lets the
    binding stay decoupled from the concrete CoachingCardViewModel
    class."""

    def set_verbosity(self, level: str) -> None: ...


def bind_coaching_verbosity_to_mode_engine(
    engine: ModeEngine,
    *,
    target: _VerbosityTarget,
    sync_now: bool = False,
) -> None:
    """Wire ``engine`` so every mode change calls
    ``target.set_verbosity(<new_mode>.coaching_verbosity)``.

    :param sync_now: If ``True``, push the engine's *current*
        mode verbosity to the target immediately. Useful at
        app startup so the coaching subsystem honours the
        persisted mode (T117) from the first frame.
    """
    engine.on_mode_changed(
        lambda mode: target.set_verbosity(mode.coaching_verbosity)
    )
    if sync_now:
        target.set_verbosity(engine.current.coaching_verbosity)


__all__ = ["bind_coaching_verbosity_to_mode_engine"]
