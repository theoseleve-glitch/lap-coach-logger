"""Practice readiness computation, coaching nudges, and input correlation.

Pure functions -- no Qt dependencies, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lap_coach_logger.coaching.corner_insights import (
    CornerInsight,
    ranked_problem_corners,
    total_time_loss_s,
)
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
# Actionable readiness (redesign v2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReadinessAction:
    """Readiness state with a concrete suggested next action.

    States:
    - NOT_READY: < 5 laps, no models → "Drive consistently for 5 laps"
    - BUILDING:  5-10 laps, partial models → "8 more laps for confident fuel model"
    - READY:     10+ laps, core models confident → "Ready to race"

    ``blocker_type`` (corner-level sprint) classifies WHY readiness is
    low so the suggested_action points at the dominant problem:

    - "broad_inconsistency": spread across many corners / sectors
    - "one_major_corner":    a single corner dominates time on the table
    - "repeated_exit_issue": multiple corners with exit-phase loss
    - "repeated_braking_issue": multiple corners with brake-phase loss
    - "none": ready / nothing specific to fix
    """
    state: str                   # "not_ready" / "building" / "ready"
    suggested_action: str        # one-line instruction
    progress_pct: int            # 0-100 composite
    detail: dict                 # per-concern breakdown
    blocker_type: str = "none"   # see dataclass docstring


def compute_readiness_action(
    profiles: dict[str, CompoundProfile],
    pit_profile: PitProfile | None,
    lap_count: int = 0,
    consistency_std: float | None = None,
    corner_insights_history: list[list[CornerInsight]] | None = None,
) -> ReadinessAction:
    """Compute actionable readiness with a suggested next action.

    Unlike ``compute_readiness`` (per-compound), this returns a single
    unified state that drives the Practice tab UX.

    ``corner_insights_history`` (corner-level sprint): per-lap list of
    corner insights. When provided, enables smart blocker classification
    — the suggested_action will name the dominant issue instead of a
    generic "keep driving".
    """
    # Per-concern progress
    fuel_ready = any(p.confidence in ("high", "medium") and p.fuel_per_lap > 0 for p in profiles.values())
    tire_ready = any(
        isinstance(p.degradation, dict) and p.degradation.get("available")
        for p in profiles.values()
    )
    pit_ready = pit_profile is not None and pit_profile.beta_transit is not None
    consistency_ready = consistency_std is not None and consistency_std < 1.5

    concerns = {
        "fuel_model": {"ready": fuel_ready, "label": "Fuel model"},
        "tire_model": {"ready": tire_ready, "label": "Tire degradation model"},
        "pit_time":   {"ready": pit_ready,  "label": "Pit stop time"},
        "consistency": {"ready": consistency_ready, "label": "Driver consistency"},
    }
    ready_count = sum(1 for c in concerns.values() if c["ready"])
    progress = int(ready_count / len(concerns) * 100)

    blocker = classify_readiness_blocker(
        corner_insights_history=corner_insights_history or [],
        consistency_std=consistency_std,
    )

    if lap_count < 5:
        state = "not_ready"
        action = f"Drive {max(1, 5 - lap_count)} more laps to start building models"
    elif ready_count < 3:
        state = "building"
        # Corner-level insight takes priority over generic concerns once
        # the driver has enough laps for the blocker logic to matter.
        if blocker != "none":
            action = _blocker_action(blocker, corner_insights_history or [])
        else:
            missing = [c["label"] for c in concerns.values() if not c["ready"]]
            if missing:
                action = f"Building data — next: {missing[0].lower()}"
            else:
                action = "Almost ready — keep driving"
    else:
        state = "ready"
        if ready_count == len(concerns) and blocker == "none":
            action = "Ready to race. Switch to Sprint or Endurance to build your plan."
        elif blocker != "none":
            action = _blocker_action(blocker, corner_insights_history or [])
        else:
            missing = [c["label"] for c in concerns.values() if not c["ready"]]
            action = f"Ready to race ({', '.join(missing).lower()} still calibrating)"

    return ReadinessAction(
        state=state,
        suggested_action=action,
        progress_pct=progress,
        detail=concerns,
        blocker_type=blocker,
    )


# ---------------------------------------------------------------------------
# Blocker classifier (corner-level sprint)
# ---------------------------------------------------------------------------

def classify_readiness_blocker(
    *,
    corner_insights_history: list[list[CornerInsight]],
    consistency_std: float | None,
) -> str:
    """Classify WHY the driver isn't race-ready based on corner patterns.

    Returns one of:
    - "one_major_corner": a single corner dominates (>60% of total loss)
    - "repeated_exit_issue": ≥3 different corners show exit-phase loss
    - "repeated_braking_issue": ≥3 different corners show entry-phase loss
    - "broad_inconsistency": overall std dev > 0.8s, loss spread thin
    - "none": nothing significant to classify
    """
    if not corner_insights_history:
        if consistency_std is not None and consistency_std > 0.8:
            return "broad_inconsistency"
        return "none"

    # Use the most recent 5 laps of insights so stale patterns don't
    # dominate once the driver has corrected them.
    recent = corner_insights_history[-5:]
    flat = [i for lap in recent for i in lap]
    if not flat:
        return "none"

    total = total_time_loss_s(flat)
    if total < 0.15:
        return "none"

    # One-major-corner: single corner dominates ≥60% of time loss
    by_corner: dict[str, float] = {}
    for i in flat:
        if i.time_loss_s and i.time_loss_s > 0:
            by_corner[i.corner_name] = by_corner.get(i.corner_name, 0.0) + i.time_loss_s
    if by_corner and total > 0:
        top_corner, top_loss = max(by_corner.items(), key=lambda kv: kv[1])
        if top_loss / total >= 0.6:
            return "one_major_corner"

    # Repeated exit/braking: count distinct corners per loss zone
    exit_corner_names: set[str] = set()
    entry_corner_names: set[str] = set()
    for i in flat:
        if i.time_loss_s is None or i.time_loss_s < 0.1:
            continue
        if i.loss_zone == "exit":
            exit_corner_names.add(i.corner_name)
        elif i.loss_zone == "entry":
            entry_corner_names.add(i.corner_name)
    exit_corners = len(exit_corner_names)
    entry_corners = len(entry_corner_names)
    if exit_corners >= 3 and exit_corners >= entry_corners:
        return "repeated_exit_issue"
    if entry_corners >= 3:
        return "repeated_braking_issue"

    # Broad inconsistency fallback
    if consistency_std is not None and consistency_std > 0.8:
        return "broad_inconsistency"
    # Many different corners contributing small losses
    corners_with_loss = sum(1 for v in by_corner.values() if v > 0.05)
    if corners_with_loss >= 4:
        return "broad_inconsistency"
    return "none"


def _blocker_action(
    blocker: str,
    history: list[list[CornerInsight]],
) -> str:
    """Produce a concise action sentence for the classified blocker."""
    flat = [i for lap in history[-5:] for i in lap]
    if blocker == "one_major_corner":
        top = ranked_problem_corners(flat, top_n=1, min_confidence="medium")
        if top:
            t = top[0]
            loss = t.time_loss_s or 0.0
            return f"Focus {t.corner_name} — {loss:.2f}s lost there. Fix this one corner first."
        return "One corner is costing most of your time — focus there first."
    if blocker == "repeated_exit_issue":
        return "Exit phase loss across multiple corners — work on earlier throttle pickup."
    if blocker == "repeated_braking_issue":
        return "Braking inconsistency across multiple corners — lock in a repeatable brake reference."
    if blocker == "broad_inconsistency":
        return "Broad inconsistency — run smoother, repeatable laps before chasing time."
    return "Keep driving — no dominant issue yet."


# ---------------------------------------------------------------------------
# Coaching carryover (redesign v2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoachingCarryover:
    """Coaching insights that persist across mode switches.

    When a user moves from Coaching → Sprint/Endurance, this data
    is available for lightweight reminders during the race.
    """
    focus_sector: str | None         # "Sector 2"
    focus_corner: str | None         # "T5" or None
    time_on_table_s: float           # sum of sector gaps
    consistency_std_s: float         # overall std dev
    trend: str                       # "improving" / "stable" / "degrading"
    best_lap_time_s: float | None    # reference for race
    technique_hint: str              # short reminder from coaching plan


def build_coaching_carryover(
    *,
    focus_area: str | None,
    overall_std: float,
    trend: str,
    sector_gaps_total: float = 0.0,
    best_lap_time: float | None = None,
    technique_insight: str = "",
) -> CoachingCarryover:
    """Build the carryover data from the latest coaching state."""
    focus_sector = focus_area if focus_area and focus_area.startswith("Sector") else None
    focus_corner = focus_area if focus_area and (focus_area.startswith("T") or focus_area.startswith("Turn")) else None

    # Shorten the technique insight for race-mode display
    hint = technique_insight
    if len(hint) > 80:
        hint = hint[:77] + "..."

    return CoachingCarryover(
        focus_sector=focus_sector,
        focus_corner=focus_corner,
        time_on_table_s=round(sector_gaps_total, 2),
        consistency_std_s=round(overall_std, 3),
        trend=trend,
        best_lap_time_s=best_lap_time,
        technique_hint=hint,
    )


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
