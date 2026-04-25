"""T114: Mode → strategy safety-margin binding.

Thin adapter that forwards each new :class:`Mode`'s
``strategy_safety_margin`` to a target via
``target.set_safety_margin(margin)``. Mirrors T112's overlay
binding and T113's coaching binding shape.
"""
from __future__ import annotations

from typing import Protocol

from lap_coach_logger.core.modes.engine import ModeEngine


class _SafetyMarginTarget(Protocol):
    """Structural shape of any object the binding can drive —
    just needs ``set_safety_margin(margin: float) -> None``.
    Lets the binding stay decoupled from the eventual strategy
    engine class (Block H — T136-T155)."""

    def set_safety_margin(self, margin: float) -> None: ...


def bind_strategy_safety_margin_to_mode_engine(
    engine: ModeEngine,
    *,
    target: _SafetyMarginTarget,
    sync_now: bool = False,
) -> None:
    """Wire ``engine`` so every mode change calls
    ``target.set_safety_margin(<new_mode>.strategy_safety_margin)``.

    :param sync_now: If ``True``, push the engine's *current*
        mode margin to the target immediately. Useful at app
        startup so the strategy subsystem honours the persisted
        mode (T117) from the first frame instead of waiting
        for a user-initiated mode change.
    """
    engine.on_mode_changed(
        lambda mode: target.set_safety_margin(mode.strategy_safety_margin)
    )
    if sync_now:
        target.set_safety_margin(engine.current.strategy_safety_margin)


__all__ = ["bind_strategy_safety_margin_to_mode_engine"]
