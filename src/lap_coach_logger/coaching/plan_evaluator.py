"""Plan Evaluator.

Evaluates whether a coaching plan succeeded after the evaluation
window by comparing pre- and post-plan lap/sector times.
All thresholds are proportional -- no hardcoded absolute values.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lap_coach_logger.coaching.output import Confidence, CoachingOutput

if TYPE_CHECKING:
    from lap_coach_logger.coaching.plan_engine import CoachingPlan


@dataclass(frozen=True)
class PlanResult:
    success: bool
    delta_vs_target: float      # negative = beat target, positive = missed
    updated_std_dev: float      # std dev of focus area in evaluation window
    next_action: str            # "continue" | "change_focus" | "advance"
    confidence: Confidence
    reason: str


def _std_dev(values: list[float]) -> float:
    """Sample standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _parse_target_std(measurable_target: str) -> float | None:
    """Extract the target std dev number from the measurable_target string.

    Expected format: "... to +/-X.XXXs"
    """
    match = re.search(r"to\s*\u00b1?([\d.]+)s", measurable_target)
    if match:
        return float(match.group(1))
    return None


def evaluate_plan(
    plan: CoachingPlan,
    pre_laps: list[float],
    post_laps: list[float],
) -> CoachingOutput:
    """Evaluate a coaching plan by comparing pre and post lap data.

    Returns a CoachingOutput whose value is a PlanResult.
    """
    # ---- Gate: not enough data ----
    if len(post_laps) < plan.evaluation_window:
        return CoachingOutput(
            value=PlanResult(
                success=False,
                delta_vs_target=0.0,
                updated_std_dev=0.0,
                next_action="continue",
                confidence=Confidence.LOW,
                reason="Not enough laps to evaluate",
            ),
            confidence=Confidence.LOW,
            reason="Not enough laps to evaluate",
        )

    pre_std = _std_dev(pre_laps) if pre_laps else 0.0
    post_std = _std_dev(post_laps)

    # Parse the target from the plan
    target_std = _parse_target_std(plan.measurable_target)
    if target_std is None:
        target_std = pre_std * 0.7  # fallback: 30% improvement

    delta_vs_target = post_std - target_std

    # Compute proportional improvement ratio
    if pre_std > 0:
        improvement_ratio = (pre_std - post_std) / pre_std
    else:
        improvement_ratio = 0.0

    # Evaluate outcome based on proportional improvement
    if improvement_ratio >= 0.20:
        # 20%+ improvement: success, advance to next focus
        success = True
        next_action = "advance"
        confidence = Confidence.HIGH
        reason = (
            f"Improved by {improvement_ratio:.0%} "
            f"(std dev {round(pre_std, 3)}s -> {round(post_std, 3)}s). "
            f"Focus area: {plan.focus_area}"
        )
    elif improvement_ratio > 0:
        # Partial improvement (<20%): keep working
        success = False
        next_action = "continue"
        confidence = Confidence.MEDIUM
        reason = (
            f"Partial improvement of {improvement_ratio:.0%} "
            f"(std dev {round(pre_std, 3)}s -> {round(post_std, 3)}s). "
            f"Keep working on {plan.focus_area}"
        )
    else:
        # Got worse: continue with adjusted expectations
        success = False
        next_action = "continue"
        confidence = Confidence.LOW
        reason = (
            f"Variance increased "
            f"(std dev {round(pre_std, 3)}s -> {round(post_std, 3)}s). "
            f"Reassess approach for {plan.focus_area}"
        )

    result = PlanResult(
        success=success,
        delta_vs_target=round(delta_vs_target, 3),
        updated_std_dev=round(post_std, 3),
        next_action=next_action,
        confidence=confidence,
        reason=reason,
    )

    return CoachingOutput(
        value=result,
        confidence=confidence,
        reason=reason,
    )
