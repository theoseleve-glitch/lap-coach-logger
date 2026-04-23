"""Post-session coaching summary — compact end-of-session rollup.

Aggregates the per-lap corner insights history captured during a session
into a small, glanceable summary. No prose — just the data points a
driver needs to decide what to work on next time.

Design:
- Pure, deterministic, no Qt.
- Fixed-width outputs (top 3 problems, one primary focus, one biggest
  time-on-table area).
- Uses ``corner_insights`` helpers to avoid duplicating logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from lap_coach_logger.coaching.corner_insights import (
    CornerInsight,
    build_technique_statement,
    total_time_loss_s,
)


@dataclass(frozen=True)
class ProblemZone:
    """One row of the top-3 recurring problem list."""
    corner_name: str
    total_loss_s: float          # cumulative time loss across the session
    dominant_zone: str           # "entry" / "mid" / "exit" / "even"
    lap_count: int               # laps where this corner appeared with significant loss
    sample_insight: CornerInsight  # latest insight for this corner (drives action text)


@dataclass(frozen=True)
class PostSessionSummary:
    """Compact, glanceable end-of-session rollup."""
    problem_zones: list[ProblemZone]  # max 3 — empty when no significant loss
    largest_loss_area: str            # "T5 exit" / "Sector 2" / "" when empty
    largest_loss_s: float             # seconds the biggest single area is worth
    primary_next_session_focus: str   # short sentence — the one thing to work on
    total_time_on_table_s: float      # sum of losses across all corners
    lap_sample_count: int             # laps that contributed to the summary


def build_post_session_summary(
    corner_insights_history: list[list[CornerInsight]],
) -> PostSessionSummary:
    """Build the session summary from the per-lap corner insights history.

    Returns a summary with empty problem_zones when there's no
    significant loss data (fewer than 3 laps or no corners above the
    noise floor).
    """
    if not corner_insights_history:
        return _empty_summary(lap_count=0)

    if len(corner_insights_history) < 3:
        return _empty_summary(lap_count=len(corner_insights_history))

    flat = [i for lap in corner_insights_history for i in lap]
    total = total_time_loss_s(flat)

    # Aggregate per-corner cumulative loss, lap counts, zones, and latest
    cumulative: dict[str, float] = {}
    lap_counts: dict[str, int] = {}
    latest_by_corner: dict[str, CornerInsight] = {}
    zones_by_corner: dict[str, dict[str, int]] = {}
    for lap_insights in corner_insights_history:
        for i in lap_insights:
            if i.time_loss_s is None or i.time_loss_s < 0.08:
                continue
            cumulative[i.corner_name] = cumulative.get(i.corner_name, 0.0) + i.time_loss_s
            lap_counts[i.corner_name] = lap_counts.get(i.corner_name, 0) + 1
            latest_by_corner[i.corner_name] = i
            zones = zones_by_corner.setdefault(i.corner_name, {})
            zones[i.loss_zone] = zones.get(i.loss_zone, 0) + 1

    if not cumulative:
        return _empty_summary(lap_count=len(corner_insights_history))

    # Top 3 by cumulative loss
    ranked = sorted(cumulative.items(), key=lambda kv: kv[1], reverse=True)[:3]
    problem_zones: list[ProblemZone] = []
    for name, loss in ranked:
        zone_counts = zones_by_corner.get(name, {})
        dominant_zone = (
            max(zone_counts.items(), key=lambda kv: kv[1])[0]
            if zone_counts else "even"
        )
        problem_zones.append(ProblemZone(
            corner_name=name,
            total_loss_s=round(loss, 3),
            dominant_zone=dominant_zone,
            lap_count=lap_counts.get(name, 0),
            sample_insight=latest_by_corner[name],
        ))

    # Biggest single area = top corner + its dominant zone
    top = problem_zones[0]
    if top.dominant_zone in ("entry", "mid", "exit"):
        largest_loss_area = f"{top.corner_name} {top.dominant_zone}"
    else:
        largest_loss_area = top.corner_name

    # Primary next-session focus = actionable hint from the top corner
    primary_focus = _build_primary_focus(top)

    return PostSessionSummary(
        problem_zones=problem_zones,
        largest_loss_area=largest_loss_area,
        largest_loss_s=round(top.total_loss_s, 3),
        primary_next_session_focus=primary_focus,
        total_time_on_table_s=round(total, 3),
        lap_sample_count=len(corner_insights_history),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_summary(lap_count: int) -> PostSessionSummary:
    return PostSessionSummary(
        problem_zones=[],
        largest_loss_area="",
        largest_loss_s=0.0,
        primary_next_session_focus="Not enough data for a summary — need at least 3 laps.",
        total_time_on_table_s=0.0,
        lap_sample_count=lap_count,
    )


def _build_primary_focus(top: ProblemZone) -> str:
    """Build the one-line primary focus sentence for the top problem zone."""
    statement = build_technique_statement(top.sample_insight)
    if statement is not None:
        return (
            f"Next session: focus on {top.corner_name} "
            f"({top.total_loss_s:.1f}s lost across {top.lap_count} laps). "
            f"{statement.action}."
        )
    return (
        f"Next session: focus on {top.corner_name} "
        f"({top.total_loss_s:.1f}s lost across {top.lap_count} laps)."
    )


def summary_to_dict(summary: PostSessionSummary) -> dict:
    """Convert the summary to a QML/JSON-friendly dict.

    Always includes a ``presentation`` block — a 3-line glanceable form
    the UI can bind to without doing any formatting itself.
    """
    return {
        "problem_zones": [
            {
                "corner_name": z.corner_name,
                "total_loss_s": z.total_loss_s,
                "dominant_zone": z.dominant_zone,
                "lap_count": z.lap_count,
            }
            for z in summary.problem_zones
        ],
        "largest_loss_area": summary.largest_loss_area,
        "largest_loss_s": summary.largest_loss_s,
        "primary_next_session_focus": summary.primary_next_session_focus,
        "total_time_on_table_s": summary.total_time_on_table_s,
        "lap_sample_count": summary.lap_sample_count,
        "presentation": build_summary_presentation(summary),
    }


def build_summary_presentation(summary: PostSessionSummary) -> dict:
    """Build the 3-line glanceable presentation of the summary.

    Thin adapter over the unified ``CoachingMessage`` so the
    post-session card speaks the same language as the overlay and
    Coaching tab. Lazy import avoids a cycle with presentation.py.

    Keys:
    - ``top_issues``: "T5 (0.9s), T3 (0.5s), T8 (0.3s)" or "" when empty.
    - ``biggest_loss``: "T5 exit — 0.9s" or "".
    - ``next_focus``: "Earlier throttle at T5" or a gentle fallback.
    """
    from lap_coach_logger.coaching.presentation import message_from_summary

    supporting = message_from_summary(summary).supporting
    return {
        "top_issues": supporting.get("top_issues", ""),
        "biggest_loss": supporting.get("biggest_loss", ""),
        "next_focus": supporting.get("next_focus", ""),
    }
