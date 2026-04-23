"""Strategy runtime tunables — one place to find the thresholds.

Before this module, strategy constants (fuel margins, pit windows,
divergence gates, push/manage thresholds) were scattered across
``overlay_derived``, ``race_strategy``, and ad-hoc magic numbers in the
VMs. They now live here so tuning happens in one place and callers
share consistent defaults.

Relationship with ``overlay_derived.ClassCalibration`` (kept explicit
to avoid accidental duplication):

- ``StrategyConfig`` is the **protocol tunable** layer: pit window,
  alert repeat cadence, recalc throttling, divergence tolerance, and
  the absolute DEFICIT floor that no car class should cross.
- ``ClassCalibration`` is the **per-car band tuning** layer: per-class
  fuel margins for SAFE / TIGHT / SAVE that scale with typical burn
  rate. GT4 drivers have a different "SAFE" than LMP2 drivers.

They deliberately do not collapse into one object — the domains are
meaningfully separate. The narrow overlap is the DEFICIT boundary:
``compute_fuel_state`` uses ``FUEL_SAVE_MARGIN_L`` for "below this is
deficit" and that constant now sources from
``StrategyConfig.fuel_deficit_margin_l`` so protocol config wins when
the two layers touch.

No user-facing settings yet — pure code-level config. Per-class
overrides where justified (fuel margins scale with per-lap burn).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyConfig:
    """Tunables for the in-race strategy engine.

    Fields:
    - ``pit_window_laps``: pit_countdown widget visibility horizon.
    - ``critical_alert_repeat_s``: minimum seconds between identical
      critical alerts (prevents "PIT NOW" spam).
    - ``recalc_min_interval_s``: minimum seconds between live
      recalculations. Guards against jitter when laps are short.
    - ``divergence_lap_tolerance``: ±laps we allow before flagging the
      plan as diverged.
    - ``fuel_save_margin_l``: margin below which SAVE state fires.
    - ``fuel_deficit_margin_l``: margin below which DEFICIT state fires.
    - ``stint_bounce_guard_laps``: refuse to flip pit-call state more
      than once within this many laps (prevents 3↔2↔3 oscillation).
    """
    pit_window_laps: int = 5
    critical_alert_repeat_s: float = 20.0
    recalc_min_interval_s: float = 1.5
    divergence_lap_tolerance: int = 1
    fuel_save_margin_l: float = 0.5
    fuel_deficit_margin_l: float = 0.0
    stint_bounce_guard_laps: int = 0


DEFAULT_STRATEGY = StrategyConfig()
