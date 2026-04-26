"""Per-widget feature-usage metrics (T226).

Tracks "which overlay widgets do users actually use?" by
emitting PostHog events on enable / disable / use, and by
maintaining per-session counters for shutdown summary logs.

Dispatch goes through ``analytics.track`` so the safety
guarantees (never raises, no-op when not configured) propagate
unchanged. Optional context properties (``sim``, ``mode``) are
omitted when unset rather than sent as empty strings — PostHog
"is set" filters lose meaning if every event carries them.

Wiring this into the actual overlay toggle UI is deliberate
follow-up scope; T226 establishes the dispatch primitives and
event schema so the integration is one-line per call site.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from lap_coach_logger import analytics

_widgets_enabled: dict[str, int] = defaultdict(int)
_widgets_disabled: dict[str, int] = defaultdict(int)


def _props(
    widget_id: str,
    *,
    sim: str | None,
    mode: str | None,
) -> dict[str, Any]:
    """Build the PostHog property dict, omitting unset optional
    context fields so dashboard "is set" filters work."""
    p: dict[str, Any] = {"widget_id": widget_id}
    if sim is not None:
        p["sim"] = sim
    if mode is not None:
        p["mode"] = mode
    return p


def record_widget_enabled(
    widget_id: str,
    *,
    sim: str | None = None,
    mode: str | None = None,
) -> None:
    """Emit a ``widget_enabled`` PostHog event and bump the
    per-session enable counter."""
    _widgets_enabled[widget_id] += 1
    analytics.track("widget_enabled", **_props(widget_id, sim=sim, mode=mode))


def record_widget_disabled(
    widget_id: str,
    *,
    sim: str | None = None,
    mode: str | None = None,
) -> None:
    """Emit a ``widget_disabled`` PostHog event and bump the
    per-session disable counter."""
    _widgets_disabled[widget_id] += 1
    analytics.track("widget_disabled", **_props(widget_id, sim=sim, mode=mode))


def record_widget_used(
    widget_id: str,
    *,
    sim: str | None = None,
    mode: str | None = None,
) -> None:
    """Emit a ``widget_used`` PostHog event for arbitrary user
    interaction (click / drag / etc.). Not counted in the
    enable/disable session counters — those are lifecycle
    events, this is interaction telemetry."""
    analytics.track("widget_used", **_props(widget_id, sim=sim, mode=mode))


def session_snapshot() -> dict[str, dict[str, int]]:
    """Per-session counter dump for the shutdown summary log.
    Returns plain dicts (not defaultdicts) so JSON serialization
    is unambiguous."""
    return {
        "widgets_enabled": dict(_widgets_enabled),
        "widgets_disabled": dict(_widgets_disabled),
    }


def reset_session_counters() -> None:
    """Zero both per-widget counters (process restart + tests)."""
    _widgets_enabled.clear()
    _widgets_disabled.clear()


__all__ = [
    "record_widget_enabled",
    "record_widget_disabled",
    "record_widget_used",
    "session_snapshot",
    "reset_session_counters",
]
