"""Practice readiness computation, coaching nudges, and input correlation.

Pure functions -- no Qt dependencies, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lap_coach_logger.core.stint_store import CompoundProfile
from lap_coach_logger.core.strategy_models import PitProfile


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------

_HIGH_CONFIDENCE_LAPS = 30
_WARMUP_STINTS_NEEDED = 3
_THERMAL_LAPS_NEEDED = 5


def compute_readiness(
    profiles: dict[str, CompoundProfile],
    pit_profile: PitProfile | None,
) -> dict[str, dict]:
    """Per-compound readiness percentage (0-100).

    Each of the four criteria contributes +25 %:
      * thermal model available
      * warmup model fitted
      * degradation model available
      * confidence == "high" (30+ laps)

    Returns a dict keyed by compound name.
    """
    result: dict[str, dict] = {}
    for name, prof in profiles.items():
        thermal_ok = (
            isinstance(prof.thermal, dict)
            and prof.thermal.get("available") is True
        )
        warmup_ok = (
            isinstance(prof.warmup, dict)
            and prof.warmup.get("fitted") is True
        )
        degradation_ok = (
            isinstance(prof.degradation, dict)
            and prof.degradation.get("available") is True
        )
        confidence_ok = prof.confidence == "high"

        pct = 0
        if thermal_ok:
            pct += 25
        if warmup_ok:
            pct += 25
        if degradation_ok:
            pct += 25
        if confidence_ok:
            pct += 25

        laps_needed = max(0, _HIGH_CONFIDENCE_LAPS - prof.total_laps_logged)
        stints_needed = max(0, _WARMUP_STINTS_NEEDED - prof.stint_count)

        result[name] = {
            "readiness_pct": pct,
            "thermal": thermal_ok,
            "warmup": warmup_ok,
            "degradation": degradation_ok,
            "confidence": prof.confidence,
            "total_laps_logged": prof.total_laps_logged,
            "stint_count": prof.stint_count,
            "laps_needed_for_high": laps_needed,
            "stints_needed_for_warmup": stints_needed,
        }
    return result


# ---------------------------------------------------------------------------
# Nudges
# ---------------------------------------------------------------------------

_MAX_NUDGES = 5


def compute_nudges(
    profiles: dict[str, CompoundProfile],
    pit_profile: PitProfile | None,
    available_compounds: list[str],
) -> list[str]:
    """Ordered list of max 5 actionable practice suggestions."""
    nudges: list[str] = []

    # 1. Compounds with no data at all
    for cmp in available_compounds:
        if cmp not in profiles:
            nudges.append(f"Run at least 10 laps on {cmp} tires")

    # 2. Low confidence compounds
    for cmp, prof in profiles.items():
        if prof.confidence != "high":
            needed = _HIGH_CONFIDENCE_LAPS - prof.total_laps_logged
            if needed > 0:
                nudges.append(
                    f"Run {needed} more laps on {cmp} for high confidence"
                )

    # 3. Missing warmup model (stint_count < 3)
    for cmp, prof in profiles.items():
        if prof.stint_count < _WARMUP_STINTS_NEEDED:
            needed = _WARMUP_STINTS_NEEDED - prof.stint_count
            nudges.append(
                f"Do {needed} more full stints on {cmp} (pit-to-pit)"
            )

    # 4. Missing thermal model (< 5 laps)
    for cmp, prof in profiles.items():
        has_thermal = (
            isinstance(prof.thermal, dict)
            and prof.thermal.get("available") is True
        )
        if not has_thermal and prof.total_laps_logged < _THERMAL_LAPS_NEEDED:
            needed = _THERMAL_LAPS_NEEDED - prof.total_laps_logged
            nudges.append(
                f"Run {needed} more laps on {cmp} for thermal model"
            )

    # 5. No pit profile
    if pit_profile is None or pit_profile.beta_transit is None:
        nudges.append("Do a pit stop to calibrate pit lane time")
    elif pit_profile.beta_fuel_rate is None:
        # 6. Pit profile exists but no fuel rate
        nudges.append(
            "Do another pit stop with different fuel to calibrate fuel fill rate"
        )

    # 7. Everything available -- race-ready
    if not nudges:
        nudges.append("You're race-ready! Head to Build Strategy")

    return nudges[:_MAX_NUDGES]


# ---------------------------------------------------------------------------
# Input-consumption correlation
# ---------------------------------------------------------------------------

@dataclass
class InputCorrelation:
    input_name: str
    input_value: float
    fuel_impact_l: float
    wear_impact_pct: float
    suggestion: Optional[str]


_FUEL_THRESHOLD = 0.05   # litres per lap
_WEAR_THRESHOLD = 0.5    # % per lap


def correlate_inputs_consumption(
    input_metrics: list[dict],
    fuel_deltas: list[float],
    wear_rates: list[float],
) -> list[InputCorrelation]:
    """Correlate driving style with consumption.

    Returns empty list if fewer than 3 laps of data.
    """
    n = min(len(input_metrics), len(fuel_deltas), len(wear_rates))
    if n < 3:
        return []

    # Find best (most efficient) lap as baseline
    best_idx = 0
    best_cost = fuel_deltas[0] + wear_rates[0]
    for i in range(1, n):
        cost = fuel_deltas[i] + wear_rates[i]
        if cost < best_cost:
            best_cost = cost
            best_idx = i

    baseline_metrics = input_metrics[best_idx]
    baseline_fuel = fuel_deltas[best_idx]
    baseline_wear = wear_rates[best_idx]

    # Gather all input keys from the first entry
    input_keys = sorted(input_metrics[0].keys())

    results: list[InputCorrelation] = []
    for key in input_keys:
        values = [input_metrics[i].get(key, 0.0) for i in range(n)]
        avg_value = sum(values) / n
        baseline_value = baseline_metrics.get(key, 0.0)

        # Average impact relative to baseline
        avg_fuel = sum(fuel_deltas[:n]) / n
        avg_wear = sum(wear_rates[:n]) / n
        fuel_impact = avg_fuel - baseline_fuel
        wear_impact = avg_wear - baseline_wear

        suggestion: Optional[str] = None
        if fuel_impact > _FUEL_THRESHOLD:
            suggestion = f"Reducing {key} could save ~{fuel_impact:.2f} L/lap in fuel"
        elif wear_impact > _WEAR_THRESHOLD:
            suggestion = f"Reducing {key} could save ~{wear_impact:.1f}%/lap in tire wear"

        results.append(
            InputCorrelation(
                input_name=key,
                input_value=avg_value,
                fuel_impact_l=round(fuel_impact, 3),
                wear_impact_pct=round(wear_impact, 3),
                suggestion=suggestion,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Race statistics
# ---------------------------------------------------------------------------

def compute_race_statistics(
    plan_stints: list[dict],
    profiles: dict[str, CompoundProfile],
    fuel_capacity: float,
    total_race_time_s: float,
    fuel_at_finish: float,
) -> dict:
    """Compute race stats from an optimised plan.

    Each stint dict is expected to contain at least:
        ``compound``, ``start_lap``, ``end_lap``, ``stint_time_s``,
        ``grip_at_end``.
    """
    if not plan_stints:
        return {}

    estimated_laps = plan_stints[-1].get("end_lap", 0)
    pit_stops = max(0, len(plan_stints) - 1)

    # Qualifying target: best compound's avg_lap_time_s
    qualifying_target_s = min(
        (p.avg_lap_time_s for p in profiles.values()),
        default=0.0,
    )

    # Race pace target: total stint time / estimated laps
    total_stint_time = sum(s.get("stint_time_s", 0.0) for s in plan_stints)
    race_pace_target_s = (
        total_stint_time / estimated_laps if estimated_laps > 0 else 0.0
    )

    best_case_time_s = total_race_time_s * 0.97
    worst_case_time_s = total_race_time_s * 1.05

    grip_at_finish_pct = plan_stints[-1].get("grip_at_end", 0.0)

    return {
        "estimated_laps": estimated_laps,
        "estimated_race_time_s": total_race_time_s,
        "pit_stops": pit_stops,
        "qualifying_target_s": qualifying_target_s,
        "race_pace_target_s": race_pace_target_s,
        "best_case_time_s": best_case_time_s,
        "worst_case_time_s": worst_case_time_s,
        "fuel_margin_l": fuel_at_finish,
        "grip_at_finish_pct": grip_at_finish_pct,
    }
