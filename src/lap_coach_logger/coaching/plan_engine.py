"""Next-5-Laps Plan Engine.

Takes the current consistency analysis and produces ONE focus area
with a measurable target.  All thresholds are proportional to the
data -- nothing is hardcoded as an absolute value.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lap_coach_logger.coaching.output import Confidence, CoachingOutput
from lap_coach_logger.coaching.plan_evaluator import PlanResult
from lap_coach_logger.core.consistency_analyzer import ConsistencyReport


@dataclass(frozen=True)
class CoachingPlan:
    focus_area: str            # corner ID or sector name (e.g., "Sector 2", "T5")
    objective: str             # short action string ("Stabilize braking point")
    measurable_target: str     # quantified ("Reduce S2 std dev from +/-0.45s to +/-0.30s")
    ignore_list: list[str] = field(default_factory=list)  # what NOT to focus on
    evaluation_window: int = 5
    confidence: Confidence = Confidence.MEDIUM
    reason: str = ""


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
) -> CoachingOutput:
    """Generate a single-focus coaching plan from a consistency report.

    Returns a CoachingOutput whose value is a CoachingPlan.
    """
    # ---- Gate: insufficient data ----
    if report is None or report.lap_count < 3:
        return CoachingOutput(
            value=None,
            confidence=Confidence.LOW,
            reason="Need more laps (minimum 3) before generating a plan",
        )

    overall_std = report.overall_std_dev_s

    # ---- Determine focus area from data ----
    focus_area: str = ""
    focus_std: float = overall_std
    objective: str = ""

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
            # Corner focus when its variance is significant relative to overall
            if std > overall_std * 0.5:
                focus_area = name
                focus_std = std
                objective = "Stabilize corner entry and exit"
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
                objective = "Stabilize braking point and throttle application"
                break

    # 3. Fallback to overall consistency
    if not focus_area:
        focus_area = "Overall consistency"
        focus_std = overall_std
        objective = "Reduce lap-time variance"

    # ---- Adjust target if previous plan failed ----
    improvement_factor = 0.7  # default: target 30% improvement
    if previous_plan_result is not None and not previous_plan_result.success:
        # Ease the target to 15% improvement after a failure
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
