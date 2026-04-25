"""T107: ``PracticeMode`` — verbose coaching, minimal strategy.

Practice sessions are where drivers want **everything**: every
late-brake, every apex slip, every consistency wobble. Strategy
is irrelevant (no fuel pressure, no race-craft trade-offs), so
the safety margin is zero — the user is here to learn, not to
manage risk.
"""
from __future__ import annotations

from lap_coach_logger.core.modes.base import Mode


class PracticeMode(Mode):
    """Verbose-coaching profile for practice sessions."""

    id = "practice"
    name = "Practice"
    coaching_verbosity = "verbose"
    overlay_preset_id = "practice"
    environment_tag = "sim_practice"
    strategy_safety_margin = 0.0


__all__ = ["PracticeMode"]
