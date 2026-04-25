"""T109: ``EnduranceMode`` — long-run focus, stint awareness.

Endurance sessions (1h+: 6h Le Mans Virtual, MX-5 endurance,
team enduros) are paced races where consistency over many
laps matters more than peak speed. Coaching cadence is
"minimal" (don't fatigue the driver) but strategy is
conservative — fuel margin needs headroom for unexpected
long stints, code-60 cycles, or botched pit stops.
"""
from __future__ import annotations

from lap_coach_logger.core.modes.base import Mode


class EnduranceMode(Mode):
    """Long-run profile for endurance racing."""

    id = "endurance"
    name = "Endurance"
    coaching_verbosity = "minimal"
    overlay_preset_id = "endurance"
    environment_tag = "sim_endurance"
    # 12% — typical endurance fuel-strategy headroom: enough
    # to absorb a Code-60 lap or a slow first-out-lap, not so
    # much that the car runs short of pace.
    strategy_safety_margin = 0.12


__all__ = ["EnduranceMode"]
