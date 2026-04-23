"""Next-5-Laps Plan Engine — redesign v2.

Takes the current consistency analysis and produces ONE focus area
with a measurable target AND a concrete technique insight based on
self-comparison data.  All thresholds are proportional to the
data — nothing is hardcoded as an absolute value.

Redesign v2 changes:
- Replaces generic objectives ("Stabilize braking point") with
  data-driven coaching sentences that tell the driver WHERE they're
  losing time, HOW MUCH, and WHAT to work on.
- Adds ``technique_insight`` field to CoachingPlan.
- Accepts optional ``sector_gaps`` for quantified self-comparison.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lap_coach_logger.coaching.corner_insights import (
    CornerInsight,
    build_technique_statement,
    ranked_problem_corners,
)
from lap_coach_logger.coaching.output import Confidence, CoachingOutput
from lap_coach_logger.coaching.plan_evaluator import PlanResult
from lap_coach_logger.core.consistency_analyzer import ConsistencyReport


@dataclass(frozen=True)
class SectorGap:
    """Per-sector gap between median and best lap (seconds). Positive = time on the table."""
    sector: int            # 1-indexed
    gap_s: float           # median - best (seconds)
    std_dev_s: float       # variance in this sector
    best_time_s: float     # best sector time
    median_time_s: float   # median sector time


@dataclass(frozen=True)
class CoachingPlan:
    focus_area: str            # corner ID or sector name (e.g., "Sector 2", "T5")
    objective: str             # short action string ("Stabilize braking point")
    measurable_target: str     # quantified ("Reduce S2 std dev from +/-0.45s to +/-0.30s")
    technique_insight: str     # concrete, data-driven coaching sentence (v2)
    ignore_list: list[str] = field(default_factory=list)
    evaluation_window: int = 5
    confidence: Confidence = Confidence.MEDIUM
    reason: str = ""
    # Corner-level technique fields (sprint: Corner-Level Technique Coaching).
    # Populated when a high-confidence corner insight drives the plan; empty
    # when the plan falls back to sector-level guidance.
    corner_focus: str = ""     # "T5" when the focus is a specific corner
    technique_action: str = "" # "Brake 10m earlier" — action hint from insight
    likely_cause: str = ""     # "Rushed entry" — cause hint from insight
    # Snapshot of the focus's time loss at plan-generation time. Stable
    # across the plan's lifetime so overlay hysteresis compares apples
    # to apples instead of jittering with per-lap insight updates.
    plan_time_loss_s: float | None = None


def _build_ignore_list(
    focus: str,
    sector_count: int,
    worst_corners: list[dict],
) -> list[str]:
    """Build an explicit ignore list of everything that is NOT the focus."""
    items: list[str] = []
    for i in range(sector_count):
        label = f"Sector {i + 1}"
        if label != focus:
            items.append(f"Don't chase {label}")
    for corner in worst_corners:
        name = corner.get("name", "")
        if name and name != focus:
            items.append(f"Don't chase {name}")
    if not items:
        items.append("Don't chase lap time")
    return items


def generate_plan(
    report: ConsistencyReport | None,
    laps_completed: int,
    previous_plan_result: PlanResult | None = None,
    sector_gaps: list[SectorGap] | None = None,
    corner_insights: list[CornerInsight] | None = None,
) -> CoachingOutput:
    """Generate a single-focus coaching plan from a consistency report.

    ``sector_gaps`` (v2): per-sector gap between driver's median and best.
    When provided, coaching outputs include concrete technique insights
    instead of generic objectives.

    ``corner_insights`` (Corner-Level sprint): per-corner self-comparison
    metrics. When a high-confidence corner dominates time-on-table, the
    plan focuses on that corner instead of a sector. Falls back to
    sector-level focus when confidence is insufficient.

    Returns a CoachingOutput whose value is a CoachingPlan.
    """
    # ---- Gate: insufficient data ----
    if report is None or report.lap_count < 3:
        return CoachingOutput(
            value=None,
            confidence=Confidence.LOW,
            reason="Need more laps (minimum 3) before generating a plan",
        )

    # ---- Corner-level focus (preferred when high-confidence) ----
    corner_plan = _try_corner_focused_plan(
        report=report,
        corner_insights=corner_insights or [],
    )
    if corner_plan is not None:
        return CoachingOutput(
            value=corner_plan,
            confidence=corner_plan.confidence,
            reason=corner_plan.reason,
        )

    overall_std = report.overall_std_dev_s

    # ---- Determine focus area from data ----
    focus_area: str = ""
    focus_std: float = overall_std
    focus_sector_idx: int | None = None  # 0-indexed sector for gap lookup

    # If previous plan succeeded, skip that area and find next-worst
    skip_area: str | None = None
    if previous_plan_result is not None and previous_plan_result.success:
        skip_area = previous_plan_result.reason.split(":")[-1].strip() if ":" in previous_plan_result.reason else None

    # 1. Check worst corners first
    corner_chosen = False
    if report.worst_corners:
        for corner in report.worst_corners:
            name = corner.get("name", "")
            std = corner.get("std_dev_s", 0.0)
            if skip_area and name == skip_area:
                continue
            if std > overall_std * 0.5:
                focus_area = name
                focus_std = std
                corner_chosen = True
                break

    # 2. Fallback to worst sector
    if not corner_chosen and report.per_sector_std_dev:
        sector_stds = list(enumerate(report.per_sector_std_dev))
        sector_stds.sort(key=lambda x: x[1], reverse=True)
        for idx, std in sector_stds:
            label = f"Sector {idx + 1}"
            if skip_area and label == skip_area:
                continue
            if std > overall_std * 0.3:
                focus_area = label
                focus_std = std
                focus_sector_idx = idx
                break

    # 3. Fallback to overall consistency
    if not focus_area:
        focus_area = "Overall consistency"
        focus_std = overall_std

    # ---- Build technique insight (v2: concrete self-comparison) ----
    technique_insight = _build_technique_insight(
        focus_area=focus_area,
        focus_std=focus_std,
        focus_sector_idx=focus_sector_idx,
        sector_gaps=sector_gaps,
        overall_std=overall_std,
        trend=report.trend,
    )

    # ---- Derive objective from insight (backwards compat) ----
    # The objective is now a short summary; the insight is the detailed sentence
    if focus_sector_idx is not None and sector_gaps:
        gap = next((g for g in sector_gaps if g.sector == focus_sector_idx + 1), None)
        if gap and gap.gap_s > 0.1:
            objective = f"Close the {round(gap.gap_s, 1)}s gap in {focus_area}"
        else:
            objective = f"Stabilize {focus_area} (±{round(focus_std, 2)}s variance)"
    elif corner_chosen:
        objective = f"Stabilize {focus_area} (±{round(focus_std, 2)}s variance)"
    else:
        objective = f"Reduce overall variance (±{round(focus_std, 2)}s)"

    # ---- Adjust target if previous plan failed ----
    improvement_factor = 0.7
    if previous_plan_result is not None and not previous_plan_result.success:
        improvement_factor = 0.85

    target_std = round(focus_std * improvement_factor, 3)
    measurable_target = (
        f"Reduce {focus_area} std dev from "
        f"\u00b1{round(focus_std, 3)}s to \u00b1{target_std}s"
    )

    ignore_list = _build_ignore_list(
        focus_area,
        len(report.per_sector_std_dev),
        report.worst_corners,
    )

    # ---- Confidence from data quality ----
    if report.lap_count >= 10:
        confidence = Confidence.HIGH
    elif report.lap_count >= 5:
        confidence = Confidence.MEDIUM
    else:
        confidence = Confidence.LOW

    plan = CoachingPlan(
        focus_area=focus_area,
        objective=objective,
        measurable_target=measurable_target,
        technique_insight=technique_insight,
        ignore_list=ignore_list,
        evaluation_window=5,
        confidence=confidence,
        reason=f"Chosen because {focus_area} has the highest variance ({round(focus_std, 3)}s)",
    )

    return CoachingOutput(
        value=plan,
        confidence=confidence,
        reason=plan.reason,
    )


# ---------------------------------------------------------------------------
# Technique insight generation (v2)
# ---------------------------------------------------------------------------

def _build_technique_insight(
    *,
    focus_area: str,
    focus_std: float,
    focus_sector_idx: int | None,
    sector_gaps: list[SectorGap] | None,
    overall_std: float,
    trend: str,
) -> str:
    """Build a concrete, data-driven coaching sentence.

    Template library (~12 patterns) covers the most common amateur driver
    errors. Each template is parameterized with measured data — no AI,
    no free text, just lookup + format.
    """
    # If we have sector gap data for the focus sector, use it
    gap: SectorGap | None = None
    if focus_sector_idx is not None and sector_gaps:
        gap = next((g for g in sector_gaps if g.sector == focus_sector_idx + 1), None)

    # ---- Sector-level insights (most common path) ----
    if gap is not None and gap.gap_s > 0.05:
        # Time-on-table insight
        if gap.std_dev_s > overall_std * 0.6:
            # High variance sector with large gap
            return (
                f"{focus_area}: You lose {gap.gap_s:.1f}s here vs your best. "
                f"Variance is ±{gap.std_dev_s:.2f}s — the biggest consistency gap. "
                f"Match your best sector pace ({gap.best_time_s:.1f}s) for 3 laps straight."
            )
        elif gap.gap_s > 0.3:
            # Moderate gap, moderate variance
            return (
                f"{focus_area}: {gap.gap_s:.1f}s between your median and best. "
                f"Your best is {gap.best_time_s:.1f}s — you hit it once, "
                f"so the speed is there. Focus on repeating that entry."
            )
        else:
            # Small gap — sector is nearly optimized
            return (
                f"Good consistency in {focus_area} (±{gap.std_dev_s:.2f}s). "
                f"Only {gap.gap_s:.1f}s on the table. Move focus elsewhere."
            )

    # ---- Corner-level insights ----
    if focus_area.startswith("T") or focus_area.startswith("Turn"):
        return (
            f"{focus_area}: ±{focus_std:.2f}s variance. "
            f"This corner is your biggest consistency issue. "
            f"Focus on hitting the same braking point every lap."
        )

    # ---- Trend-based insights ----
    if trend == "degrading":
        return (
            f"Consistency is dropping (±{overall_std:.2f}s). "
            f"{focus_area} is the main contributor. "
            f"Consider: are tires fading or are you chasing time?"
        )
    if trend == "improving":
        time_on_table = sum(g.gap_s for g in (sector_gaps or []) if g.gap_s > 0)
        if time_on_table > 0.3:
            return (
                f"Your pace is improving. {time_on_table:.1f}s still on the table — "
                f"most of it in {focus_area}."
            )
        return (
            f"Improving well. {focus_area} is your next opportunity "
            f"(±{focus_std:.2f}s variance, tightest sector)."
        )

    # ---- Fallback: overall consistency ----
    return (
        f"Overall variance: ±{overall_std:.2f}s. "
        f"Focus on {focus_area} — it has the most room for improvement."
    )


# ---------------------------------------------------------------------------
# Corner-level focus (Corner-Level Technique Coaching sprint)
# ---------------------------------------------------------------------------

def _try_corner_focused_plan(
    *,
    report: ConsistencyReport,
    corner_insights: list[CornerInsight],
) -> CoachingPlan | None:
    """Build a corner-focused plan when a dominant problem corner exists.

    Requirements for a corner-level plan (conservative — we only take
    over sector focus when we're confident):
    - At least one medium-confidence corner with ≥0.15s loss
    - Corner loss must be at least 1.5× the overall variance (otherwise
      the driver's main issue is consistency, not a single corner)
    - Enough laps for meaningful segmentation (>=5)

    Returns None when corner-level focus isn't justified, so the caller
    falls back to sector-level logic.
    """
    if report.lap_count < 5 or not corner_insights:
        return None

    ranked = ranked_problem_corners(
        corner_insights, top_n=1, min_confidence="medium",
    )
    if not ranked:
        return None

    top = ranked[0]
    if top.time_loss_s is None or top.time_loss_s < 0.15:
        return None
    # Corner loss must dominate — avoid taking over when consistency is worse
    if top.time_loss_s < report.overall_std_dev_s * 1.5:
        return None

    statement = build_technique_statement(top)
    if statement is None:
        return None

    conf_map = {
        "high": Confidence.HIGH,
        "medium": Confidence.MEDIUM,
        "low": Confidence.LOW,
    }
    plan_confidence = conf_map.get(top.confidence, Confidence.MEDIUM)

    target_loss = round(max(0.05, top.time_loss_s * 0.5), 2)
    measurable_target = (
        f"Reduce {top.corner_name} time loss from "
        f"{top.time_loss_s:.2f}s to ≤{target_loss}s vs your best"
    )

    ignore_list = [
        f"Don't chase lap time — commit to {top.corner_name}",
        "Keep inputs identical everywhere else",
    ]

    technique_insight = (
        f"{statement.focus}: {statement.observation}. "
        f"{statement.likely_cause}. {statement.action}."
    )

    return CoachingPlan(
        focus_area=top.corner_name,
        objective=statement.action,
        measurable_target=measurable_target,
        technique_insight=technique_insight,
        ignore_list=ignore_list,
        evaluation_window=5,
        confidence=plan_confidence,
        reason=f"Corner-level focus: {top.corner_name} dominates time on the table",
        corner_focus=top.corner_name,
        technique_action=statement.action,
        likely_cause=statement.likely_cause,
        plan_time_loss_s=top.time_loss_s,
    )
