"""Coaching policy configuration — single tunable home for thresholds.

Before this module existed, cooldown / carryover / hysteresis / truncation
constants were scattered across ``surface_policy`` and ``presentation``.
They now live here so tuning happens in one place and surfaces share
the same defaults without copy-paste drift.

No user-facing settings yet — callers build a ``PolicyConfig`` instance
with safe defaults and may override specific fields for tests or
surface-specific variants (e.g. a lighter cooldown in the Coaching tab).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyConfig:
    """Tunables for the coaching surface policy engine.

    Defaults match the pre-unification constants so existing behaviour
    is preserved. Callers override only what they need.

    Fields:
    - ``cooldown_s``: minimum seconds between updates to the same
      surface. Prevents distracting flashes lap-to-lap.
    - ``improvement_ratio``: new focus must beat the previous by this
      ratio of time loss to switch — anti-oscillation.
    - ``carryover_ttl_s``: how long a high-confidence focus persists
      after the underlying plan drops out (mode switch, lap boundary).
    - ``headline_max`` / ``subline_max``: hard caps for truncation.
    """
    cooldown_s: float = 15.0
    improvement_ratio: float = 1.20
    carryover_ttl_s: float = 180.0
    headline_max: int = 48
    subline_max: int = 80


# Single canonical default instance. Callers import this rather than
# constructing fresh PolicyConfigs so tuning propagates everywhere.
DEFAULT_POLICY = PolicyConfig()

# Coaching tab variant — the tab surfaces richer context and can
# tolerate lighter cooldown + longer carryover than the in-race overlay.
# Kept here so surface code doesn't invent its own tunings.
COACHING_TAB_POLICY = PolicyConfig(
    cooldown_s=5.0,
    carryover_ttl_s=600.0,
    headline_max=64,
    subline_max=140,
)

# Race overlay variant — identical to the default; named explicitly so
# callers can show intent at the call site.
RACE_OVERLAY_POLICY = DEFAULT_POLICY
