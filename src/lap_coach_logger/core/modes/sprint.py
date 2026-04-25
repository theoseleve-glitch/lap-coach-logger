"""T108: ``SprintMode`` — race coaching, simplified strategy.

Sprint races (15-30 minute formats: weekly leagues, MX-5 cups,
GT iRacing series) emphasise consistency over the few laps that
decide the result. Coaching is minimal — race-craft beats
training-mode verbosity in a 15-minute window. Strategy is
simplified: typically no pit stop, fuel margin tight but
non-zero so a slow lap doesn't DNF the driver.
"""
from __future__ import annotations

from lap_coach_logger.core.modes.base import Mode


class SprintMode(Mode):
    """Race-mode profile for short-format competitive sessions."""

    id = "sprint"
    name = "Sprint"
    coaching_verbosity = "minimal"
    overlay_preset_id = "race-minimal"
    environment_tag = "sim_sprint"
    # 5% — small enough that fuel-saving doesn't hurt pace, big
    # enough that one off-pace lap doesn't DNF the driver.
    strategy_safety_margin = 0.05


__all__ = ["SprintMode"]
