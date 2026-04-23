"""Unified coaching presentation contract.

Every coaching surface in the product (overlay, Coaching tab, race
carryover, post-session summary) renders from a single ``CoachingMessage``
dataclass. Surfaces may differ in layout and supporting detail, but
they must not contradict each other — same focus naming, same wording,
same action phrasing, same confidence semantics.

Design:
- Pure, deterministic, no Qt.
- One builder per source (plan → message, summary → message).
- Consistent truncation + severity mapping so surfaces never re-format
  the same fields independently.
- ``time_loss_s`` is ``Optional[float]`` — ``None`` means unknown,
  replacing the legacy ``-1.0`` sentinel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING

from lap_coach_logger.coaching.policy_config import DEFAULT_POLICY, PolicyConfig

if TYPE_CHECKING:
    from lap_coach_logger.coaching.plan_engine import CoachingPlan
    from lap_coach_logger.coaching.post_session_summary import PostSessionSummary


# ---------------------------------------------------------------------------
# The one contract all surfaces speak
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CoachingMessage:
    """Unified coaching content — consumed by every surface.

    Category vocabulary:
    - ``"corner"``          — a specific corner dominates the focus
    - ``"sector"``          — sector-level fallback focus
    - ``"session_summary"`` — post-session rollup
    - ``""``                — no content (empty state)

    Severity tiers:
    - ``"positive"``  — high-confidence technique hint (green tint)
    - ``"advisory"``  — medium confidence (amber tint)
    - ``"ok"``        — low confidence or generic (neutral tint)
    - ``"critical"``  — reserved for safety info (not produced here)

    ``time_loss_s`` is ``Optional[float]`` — ``None`` means the measure
    isn't available (missing insights, stale data). Surfaces that do
    hysteresis (overlay) treat ``None`` as "skip the comparison".
    """
    focus_id: str = ""
    category: str = ""
    headline: str = ""
    subline: str = ""
    confidence: str = "low"
    severity: str = "ok"
    time_loss_s: Optional[float] = None
    supporting: dict = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """True when there's nothing worth surfacing."""
        return not self.headline


# Keep surface truncation consistent across message construction sites.
# Callers pass a PolicyConfig; defaults come from policy_config.py.

def _truncate(text: str, limit: int) -> str:
    """Clamp ``text`` to ``limit`` chars, preferring a word boundary."""
    if not text or len(text) <= limit:
        return text
    head = text[: limit - 1]
    space = head.rfind(" ")
    if space > limit * 0.6:
        head = head[:space]
    return head.rstrip() + "…"


_SEVERITY_BY_CONFIDENCE = {"high": "positive", "medium": "advisory"}


def severity_for_confidence(confidence: str) -> str:
    """Map confidence tier to surface severity (used by QML tint)."""
    return _SEVERITY_BY_CONFIDENCE.get(confidence, "ok")


# ---------------------------------------------------------------------------
# Builders — turn source data into the unified message
# ---------------------------------------------------------------------------

def message_from_plan(
    plan: "CoachingPlan | None",
    *,
    time_loss_s: Optional[float] = None,
    config: PolicyConfig = DEFAULT_POLICY,
) -> CoachingMessage:
    """Build a CoachingMessage from the active coaching plan.

    Returns an empty message when ``plan`` is ``None``. ``time_loss_s``
    comes from the latest per-corner insight for this focus when
    available — callers without that signal pass ``None``.
    """
    if plan is None:
        return CoachingMessage()

    if plan.corner_focus:
        category = "corner"
    elif plan.focus_area and plan.focus_area.startswith("Sector"):
        category = "sector"
    else:
        category = ""

    confidence = getattr(plan.confidence, "value", str(plan.confidence))

    # Headline prefers the richer technique_insight; fall back to the
    # measurable objective so sector-only plans still surface something
    # meaningful.
    headline_source = plan.technique_insight or plan.objective or plan.focus_area
    subline_source = plan.technique_action or plan.objective

    return CoachingMessage(
        focus_id=plan.focus_area or "",
        category=category,
        headline=_truncate(headline_source, config.headline_max),
        subline=_truncate(subline_source, config.subline_max),
        confidence=confidence,
        severity=severity_for_confidence(confidence),
        time_loss_s=time_loss_s,
        supporting={
            "measurable_target": plan.measurable_target,
            "likely_cause": plan.likely_cause,
            "ignore_list": list(plan.ignore_list),
            "objective": plan.objective,
            "reason": plan.reason,
        },
    )


def message_from_summary(
    summary: "PostSessionSummary",
    *,
    config: PolicyConfig = DEFAULT_POLICY,
) -> CoachingMessage:
    """Build a CoachingMessage from the post-session rollup.

    The summary surface is more compact than the in-race overlay but
    uses the same headline/action phrasing style and confidence tiers.
    ``supporting`` carries the three pre-formatted lines so QML doesn't
    format them a second time.
    """
    next_focus = _short_next_focus(summary.primary_next_session_focus)

    if not summary.problem_zones:
        return CoachingMessage(
            focus_id="session_summary",
            category="session_summary",
            headline=_truncate(next_focus, config.headline_max),
            confidence="low",
            supporting={"top_issues": "", "biggest_loss": "", "next_focus": next_focus},
        )

    top = summary.problem_zones[0]
    confidence = "high" if top.lap_count >= 3 else "medium"
    top_issues = ", ".join(
        f"{z.corner_name} ({z.total_loss_s:.1f}s)" for z in summary.problem_zones
    )
    biggest_loss = (
        f"{summary.largest_loss_area} — {summary.largest_loss_s:.1f}s"
        if summary.largest_loss_area else ""
    )
    headline = summary.largest_loss_area or top.corner_name

    return CoachingMessage(
        focus_id=top.corner_name,
        category="session_summary",
        headline=_truncate(headline, config.headline_max),
        subline=_truncate(next_focus, config.subline_max),
        confidence=confidence,
        severity=severity_for_confidence(confidence),
        time_loss_s=summary.largest_loss_s if summary.largest_loss_s > 0 else None,
        supporting={
            "top_issues": top_issues,
            "biggest_loss": biggest_loss,
            "next_focus": next_focus,
            "primary_next_session_focus": summary.primary_next_session_focus,
            "total_time_on_table_s": summary.total_time_on_table_s,
        },
    )


def _short_next_focus(text: str) -> str:
    """Collapse a multi-sentence focus string to its trailing action."""
    parts = [p.strip() for p in text.split(". ") if p.strip()] if text else []
    if not parts:
        return ""
    if len(parts) >= 2:
        return parts[-1].rstrip(".") + "."
    return parts[0]


# ---------------------------------------------------------------------------
# Serialisation helpers (QML bindings + tests)
# ---------------------------------------------------------------------------

def message_to_dict(message: CoachingMessage) -> dict[str, Any]:
    """Convert a ``CoachingMessage`` to a QML/JSON-friendly dict."""
    return {
        "focus_id": message.focus_id,
        "category": message.category,
        "headline": message.headline,
        "subline": message.subline,
        "confidence": message.confidence,
        "severity": message.severity,
        "time_loss_s": message.time_loss_s,
        "supporting": dict(message.supporting),
        "is_empty": message.is_empty,
    }
