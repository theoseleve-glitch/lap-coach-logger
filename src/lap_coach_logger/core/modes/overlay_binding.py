"""T112: Mode → overlay preset binding.

Thin adapter that forwards each new :class:`Mode`'s
``overlay_preset_id`` to a target object. Production wiring
composes this against the QML overlay system; tests inject a
list-recording stub.
"""
from __future__ import annotations

from typing import Protocol

from lap_coach_logger.core.modes.engine import ModeEngine


class _PresetTarget(Protocol):
    """Structural shape of any object the binding can drive —
    just needs ``set_preset(preset_id: str) -> None``. Lets the
    binding stay decoupled from the QML overlay system's exact
    class."""

    def set_preset(self, preset_id: str) -> None: ...


def bind_overlay_preset_to_mode_engine(
    engine: ModeEngine,
    *,
    target: _PresetTarget,
    sync_now: bool = False,
) -> None:
    """Wire ``engine`` so that every mode change calls
    ``target.set_preset(<new_mode>.overlay_preset_id)``.

    :param sync_now: If ``True``, immediately push the engine's
        *current* mode preset to the target as well. Useful at
        app startup so the overlay renders the correct preset
        from the first frame instead of waiting for a user-
        initiated mode change.
    """
    engine.on_mode_changed(
        lambda mode: target.set_preset(mode.overlay_preset_id)
    )
    if sync_now:
        target.set_preset(engine.current.overlay_preset_id)


__all__ = ["bind_overlay_preset_to_mode_engine"]
