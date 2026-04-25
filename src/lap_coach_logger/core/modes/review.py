"""T110: ``ReviewMode`` — no live coaching, readiness guidance.

Desktop's playback / post-session-view profile. The user is
studying a past session, not driving live — coaching cards
have nothing to fire on, strategy assumptions don't apply.
The only mode where ``coaching_verbosity == "off"``.
"""
from __future__ import annotations

from lap_coach_logger.core.modes.base import Mode


class ReviewMode(Mode):
    """Playback / post-session profile."""

    id = "review"
    name = "Review"
    coaching_verbosity = "off"
    overlay_preset_id = "race-minimal"  # quietest of the live presets
    environment_tag = "sim_review"
    strategy_safety_margin = 0.0


__all__ = ["ReviewMode"]
