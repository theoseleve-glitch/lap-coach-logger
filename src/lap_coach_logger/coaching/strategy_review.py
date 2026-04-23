"""Post-session strategy review — "did I follow the plan?"

Turns raw plan-vs-actual state into a compact, race-engineer-style
verdict. Three to five rows max, no giant reports. Answers the core
questions a driver asks at the end of a race:

1. Did I follow the plan?
2. Where did it diverge?
3. Did strategy cost or save me time?
4. What would I do next time?

Pure, deterministic, no Qt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from lap_coach_logger.core.race_strategy import RacePlan


# ---------------------------------------------------------------------------
# Divergence classification vocabulary
# ---------------------------------------------------------------------------

# Stable string constants so downstream consumers (QML, tests) don't
# couple to free-form text.
VERDICT_ON_PLAN = "on_plan"
VERDICT_ADJUSTED = "adjusted"             # minor divergence (≤1 lap or ≤2L)
VERDICT_DIVERGED = "diverged"             # material divergence
VERDICT_NO_PLAN = "no_plan"
VERDICT_INSUFFICIENT = "insufficient"     # degraded — not enough data

DIVERGENCE_NONE = "none"
DIVERGENCE_EARLY_STOP = "early_stop"
DIVERGENCE_LATE_STOP = "late_stop"
DIVERGENCE_EXTRA_STOP = "extra_stop"
DIVERGENCE_SKIPPED_STOP = "skipped_stop"
DIVERGENCE_UNDER_FUELED = "under_fueled"
DIVERGENCE_OVER_FUELED = "over_fueled"


# Thresholds — tuned so that "close enough" doesn't generate false
# divergence flags. Kept together so tuning is in one place.
_LAP_TOLERANCE = 1              # ±1 lap from planned stop lap is "adjusted"
_FUEL_TOLERANCE_L = 2.0         # ±2L per stop is "adjusted"


@dataclass(frozen=True)
class StrategyReview:
    """Compact post-session strategy verdict.

    Field cheat-sheet:
    - ``verdict``: one of ``VERDICT_*`` — drives headline wording.
    - ``planned_stops`` / ``actual_stops``: counts; differ → extra/skipped.
    - ``biggest_divergence``: one of ``DIVERGENCE_*`` with optional detail.
    - ``fuel_variance_l``: actual - planned fuel added total (positive =
      over-fueled).
    - ``next_time_suggestion``: short, action-oriented sentence.
    - ``rows``: pre-formatted presentation rows (≤5) for the QML card.
    - ``degraded``: ``True`` when data was insufficient for a useful verdict.
    """
    verdict: str = VERDICT_INSUFFICIENT
    planned_stops: int = 0
    actual_stops: int = 0
    biggest_divergence: str = DIVERGENCE_NONE
    biggest_divergence_detail: str = ""
    fuel_variance_l: float = 0.0
    next_time_suggestion: str = ""
    rows: tuple[str, ...] = field(default_factory=tuple)
    degraded: bool = True


def build_strategy_review(
    *,
    original_plan: Optional[RacePlan],
    actual_pit_laps: list[int],
    actual_fuel_added: list[float],
    final_fuel_l: float = 0.0,
) -> StrategyReview:
    """Build a post-session strategy verdict from plan-vs-actual state.

    Arguments mirror the strategy VM's captured state — no additional
    analysis, just deterministic classification + one-line summaries.
    Returns a degraded ``StrategyReview`` when ``original_plan`` is
    missing or the race clearly didn't run through the plan.
    """
    if original_plan is None or not original_plan.stints:
        return StrategyReview(
            verdict=VERDICT_NO_PLAN,
            next_time_suggestion="No race plan was built — build a plan before the race.",
            rows=("No plan recorded for this session.",),
            degraded=True,
        )

    planned_stops = max(0, len(original_plan.stints) - 1)
    actual_stops = len(actual_pit_laps)

    planned_pit_laps = [s.end_lap for s in original_plan.stints[:-1]]
    planned_fuel_total = sum(s.fuel_to_add for s in original_plan.stints[1:])
    actual_fuel_total = sum(actual_fuel_added)
    fuel_variance_l = round(actual_fuel_total - planned_fuel_total, 2)

    # Edge case: plan existed but race barely started → degraded
    if planned_stops > 0 and actual_stops == 0 and final_fuel_l <= 0:
        return StrategyReview(
            verdict=VERDICT_INSUFFICIENT,
            planned_stops=planned_stops,
            actual_stops=0,
            next_time_suggestion="Not enough race data to review strategy.",
            rows=("Race incomplete — strategy review unavailable.",),
            degraded=True,
        )

    divergence, detail = _classify_divergence(
        planned_pit_laps=planned_pit_laps,
        actual_pit_laps=actual_pit_laps,
        planned_fuel_total=planned_fuel_total,
        actual_fuel_total=actual_fuel_total,
    )
    verdict = _derive_verdict(planned_stops, actual_stops, divergence, fuel_variance_l)
    rows = _build_rows(
        planned_stops=planned_stops,
        actual_stops=actual_stops,
        planned_pit_laps=planned_pit_laps,
        actual_pit_laps=actual_pit_laps,
        fuel_variance_l=fuel_variance_l,
        divergence=divergence,
        detail=detail,
    )
    next_time = _next_time_suggestion(verdict, divergence, detail, fuel_variance_l)

    return StrategyReview(
        verdict=verdict,
        planned_stops=planned_stops,
        actual_stops=actual_stops,
        biggest_divergence=divergence,
        biggest_divergence_detail=detail,
        fuel_variance_l=fuel_variance_l,
        next_time_suggestion=next_time,
        rows=rows,
        degraded=False,
    )


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

def _pluralize(count: int, noun: str) -> str:
    """Format ``{count} {noun}`` with a trailing ``s`` when count > 1."""
    return f"{count} {noun}{'s' if count > 1 else ''}"


def _classify_divergence(
    *,
    planned_pit_laps: list[int],
    actual_pit_laps: list[int],
    planned_fuel_total: float,
    actual_fuel_total: float,
) -> tuple[str, str]:
    """Return ``(divergence, detail)`` describing the biggest issue.

    Priority ladder — the first match wins:
    1. Extra stop
    2. Skipped stop
    3. Stopped early / late (material lap offset)
    4. Fuel materially off
    5. None — plan was followed
    """
    planned_n = len(planned_pit_laps)
    actual_n = len(actual_pit_laps)
    if actual_n > planned_n:
        return DIVERGENCE_EXTRA_STOP, _pluralize(actual_n - planned_n, "extra stop")
    if actual_n < planned_n:
        return DIVERGENCE_SKIPPED_STOP, _pluralize(planned_n - actual_n, "skipped stop")

    # Stop counts match — find the stop with the largest absolute timing offset.
    biggest_offset = 0
    offset_idx = -1
    for idx, (planned, actual) in enumerate(zip(planned_pit_laps, actual_pit_laps)):
        offset = actual - planned
        if abs(offset) > abs(biggest_offset):
            biggest_offset = offset
            offset_idx = idx

    if abs(biggest_offset) > _LAP_TOLERANCE:
        direction = DIVERGENCE_LATE_STOP if biggest_offset > 0 else DIVERGENCE_EARLY_STOP
        detail = f"Stop {offset_idx + 1} off by {_pluralize(abs(biggest_offset), 'lap')}"
        return direction, detail

    fuel_delta = actual_fuel_total - planned_fuel_total
    if abs(fuel_delta) > _FUEL_TOLERANCE_L:
        direction = DIVERGENCE_OVER_FUELED if fuel_delta > 0 else DIVERGENCE_UNDER_FUELED
        return direction, f"{abs(fuel_delta):.1f}L off plan"

    return DIVERGENCE_NONE, ""


_STOP_DIVERGENCES = frozenset({
    DIVERGENCE_EXTRA_STOP,
    DIVERGENCE_SKIPPED_STOP,
    DIVERGENCE_EARLY_STOP,
    DIVERGENCE_LATE_STOP,
})
_FUEL_DIVERGENCES = frozenset({DIVERGENCE_UNDER_FUELED, DIVERGENCE_OVER_FUELED})


def _derive_verdict(
    planned_stops: int,
    actual_stops: int,
    divergence: str,
    fuel_variance_l: float,
) -> str:
    """Collapse divergence signals into one of the VERDICT_* values."""
    if divergence in _STOP_DIVERGENCES:
        return VERDICT_DIVERGED
    if divergence in _FUEL_DIVERGENCES:
        # Fuel variance within 2× tolerance (4L) is "adjusted"; beyond is "diverged"
        return VERDICT_ADJUSTED if abs(fuel_variance_l) <= _FUEL_TOLERANCE_L * 2 else VERDICT_DIVERGED
    return VERDICT_ON_PLAN


def _build_rows(
    *,
    planned_stops: int,
    actual_stops: int,
    planned_pit_laps: list[int],
    actual_pit_laps: list[int],
    fuel_variance_l: float,
    divergence: str,
    detail: str,
) -> tuple[str, ...]:
    """Pre-format the ≤5 glanceable rows for the QML card.

    Row vocabulary is intentionally terse — race-engineer style.
    """
    rows: list[str] = []
    rows.append(f"Stops: planned {planned_stops}, actual {actual_stops}")
    if planned_pit_laps and actual_pit_laps:
        planned_str = ", ".join(str(l) for l in planned_pit_laps)
        actual_str = ", ".join(str(l) for l in actual_pit_laps)
        rows.append(f"Pit laps — planned: {planned_str}; actual: {actual_str}")
    if fuel_variance_l != 0:
        sign = "+" if fuel_variance_l > 0 else "−"
        rows.append(f"Fuel variance: {sign}{abs(fuel_variance_l):.1f}L vs plan")
    if divergence != DIVERGENCE_NONE and detail:
        rows.append(f"Biggest divergence: {detail}")
    return tuple(rows[:5])


def _next_time_suggestion(
    verdict: str,
    divergence: str,
    detail: str,
    fuel_variance_l: float,
) -> str:
    """Concise action-oriented sentence for the "what next time" row."""
    if verdict == VERDICT_ON_PLAN:
        return "Plan was tight — keep this strategy next time."
    fuel_delta = abs(fuel_variance_l)
    if divergence == DIVERGENCE_EXTRA_STOP:
        return "Unplanned stop ate time — review fuel burn and stint length."
    if divergence == DIVERGENCE_SKIPPED_STOP:
        return "Stretched a stint — verify the fuel + tire models allow it."
    if divergence == DIVERGENCE_EARLY_STOP:
        return f"Pitted {detail.lower()} — consider delaying next time."
    if divergence == DIVERGENCE_LATE_STOP:
        return f"Pitted {detail.lower()} — consider pitting earlier next time."
    if divergence == DIVERGENCE_OVER_FUELED:
        return f"Over-fueled by {fuel_delta:.1f}L — trim next target."
    if divergence == DIVERGENCE_UNDER_FUELED:
        return f"Under-fueled by {fuel_delta:.1f}L — add buffer next time."
    return "Review stint lengths + fuel targets against actuals."


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def review_to_dict(review: StrategyReview) -> dict[str, Any]:
    """Convert to a QML/JSON-friendly dict."""
    return {
        "verdict": review.verdict,
        "planned_stops": review.planned_stops,
        "actual_stops": review.actual_stops,
        "biggest_divergence": review.biggest_divergence,
        "biggest_divergence_detail": review.biggest_divergence_detail,
        "fuel_variance_l": review.fuel_variance_l,
        "next_time_suggestion": review.next_time_suggestion,
        "rows": list(review.rows),
        "degraded": review.degraded,
    }
