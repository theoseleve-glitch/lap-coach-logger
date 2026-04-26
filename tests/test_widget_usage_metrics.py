"""T226: Analytics — feature usage per widget (PostHog events).

Pins the per-widget feature-usage tracking primitives so we can
answer "which overlay widgets do users actually use?" — drives
deprecation decisions and prioritization.

Contract:

  - ``record_widget_enabled(widget_id, ...)`` emits a PostHog
    ``widget_enabled`` event with ``widget_id`` plus optional
    ``sim`` / ``mode`` context properties.
  - ``record_widget_disabled(widget_id, ...)`` emits the mirror
    ``widget_disabled`` event.
  - Both are safe no-ops when analytics is not configured (we
    never raise at instrumentation sites — analytics outages
    must not crash the app, mirroring ``analytics.track``).
  - ``record_widget_used`` is a one-shot heartbeat for any
    user interaction (not persisted as enable/disable). Useful
    for "feature touched in this session" funnels.
  - Per-session in-memory counters track how many times each
    widget was enabled this run (for shutdown summary logging).

Wiring this into the actual overlay toggle UI (OverlayManager,
overlay_window_manager, etc.) is deliberate follow-up scope —
T226 establishes the dispatch primitives and the property
schema, so the integration is one-line per call site.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from lap_coach_logger import analytics
from lap_coach_logger.analytics import widget_metrics as wm


class _RecordingPostHog:
    """Minimal PostHog stand-in that captures every capture()
    call so we can assert on event name + properties without
    needing a network."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def capture(self, *, distinct_id: str, event: str, properties: dict) -> None:
        self.calls.append(
            {"distinct_id": distinct_id, "event": event, "properties": properties}
        )


@pytest.fixture
def recording_posthog() -> Iterator[_RecordingPostHog]:
    """Wire analytics to a recording stand-in so calls become
    visible to tests; tear down so other tests aren't polluted."""
    rec = _RecordingPostHog()
    analytics.configure(
        posthog_module=rec,
        distinct_id="test-distinct-id",
        enabled=True,
    )
    wm.reset_session_counters()
    try:
        yield rec
    finally:
        analytics.reset()
        wm.reset_session_counters()


# ---------------------------------------------------------------------------
# record_widget_enabled — PostHog event shape
# ---------------------------------------------------------------------------


def test_record_widget_enabled_fires_posthog_event(
    recording_posthog: _RecordingPostHog,
) -> None:
    """Calling record_widget_enabled must emit exactly one
    PostHog capture with event name 'widget_enabled'."""
    wm.record_widget_enabled("radar_awareness")
    assert len(recording_posthog.calls) == 1
    assert recording_posthog.calls[0]["event"] == "widget_enabled"


def test_record_widget_enabled_includes_widget_id_property(
    recording_posthog: _RecordingPostHog,
) -> None:
    """The PostHog property must carry widget_id so dashboards
    can group by widget."""
    wm.record_widget_enabled("radar_awareness")
    props = recording_posthog.calls[0]["properties"]
    assert props["widget_id"] == "radar_awareness"


def test_record_widget_enabled_includes_optional_sim_property(
    recording_posthog: _RecordingPostHog,
) -> None:
    """sim is the runtime context — useful for "which widgets
    are popular in iRacing vs ACC" analysis."""
    wm.record_widget_enabled("radar_awareness", sim="iracing")
    props = recording_posthog.calls[0]["properties"]
    assert props["sim"] == "iracing"


def test_record_widget_enabled_includes_optional_mode_property(
    recording_posthog: _RecordingPostHog,
) -> None:
    """mode is the session mode (sprint / endurance / coaching /
    data) — mirrors how the rest of analytics is sliced."""
    wm.record_widget_enabled("session_delta", mode="endurance")
    props = recording_posthog.calls[0]["properties"]
    assert props["mode"] == "endurance"


def test_record_widget_enabled_omits_optional_props_when_unset(
    recording_posthog: _RecordingPostHog,
) -> None:
    """Don't ship empty-string sim/mode keys — PostHog filters
    by 'is set' lose meaning if we always send them."""
    wm.record_widget_enabled("radar_awareness")
    props = recording_posthog.calls[0]["properties"]
    assert "sim" not in props
    assert "mode" not in props


# ---------------------------------------------------------------------------
# record_widget_disabled — mirror of enabled
# ---------------------------------------------------------------------------


def test_record_widget_disabled_fires_posthog_event(
    recording_posthog: _RecordingPostHog,
) -> None:
    wm.record_widget_disabled("radar_awareness")
    assert len(recording_posthog.calls) == 1
    assert recording_posthog.calls[0]["event"] == "widget_disabled"


def test_record_widget_disabled_includes_widget_id_property(
    recording_posthog: _RecordingPostHog,
) -> None:
    wm.record_widget_disabled("spotter_awareness")
    assert recording_posthog.calls[0]["properties"]["widget_id"] == "spotter_awareness"


# ---------------------------------------------------------------------------
# record_widget_used — heartbeat for arbitrary interaction
# ---------------------------------------------------------------------------


def test_record_widget_used_fires_widget_used_event(
    recording_posthog: _RecordingPostHog,
) -> None:
    """One-shot heartbeat — used for "did the user actually
    interact with this widget?" funnels."""
    wm.record_widget_used("radar_awareness")
    assert recording_posthog.calls[0]["event"] == "widget_used"
    assert recording_posthog.calls[0]["properties"]["widget_id"] == "radar_awareness"


# ---------------------------------------------------------------------------
# Safe no-op when analytics not configured (no _RecordingPostHog wired)
# ---------------------------------------------------------------------------


def test_record_widget_enabled_is_safe_when_analytics_disabled() -> None:
    """No exception, no crash, even with analytics not wired —
    instrumentation must never bring down the host code path."""
    analytics.reset()
    # Must not raise:
    wm.record_widget_enabled("radar_awareness", sim="iracing", mode="sprint")
    wm.record_widget_disabled("radar_awareness")
    wm.record_widget_used("radar_awareness")


# ---------------------------------------------------------------------------
# Per-session counters (drives shutdown summary)
# ---------------------------------------------------------------------------


def test_session_counters_track_enable_count_per_widget(
    recording_posthog: _RecordingPostHog,
) -> None:
    """Per-session counters answer 'which widgets did this
    user enable in this run?' for the shutdown summary log."""
    wm.record_widget_enabled("radar_awareness")
    wm.record_widget_enabled("radar_awareness")
    wm.record_widget_enabled("session_delta")
    snapshot = wm.session_snapshot()
    assert snapshot["widgets_enabled"]["radar_awareness"] == 2
    assert snapshot["widgets_enabled"]["session_delta"] == 1


def test_session_counters_track_disable_count_per_widget(
    recording_posthog: _RecordingPostHog,
) -> None:
    wm.record_widget_disabled("radar_awareness")
    wm.record_widget_disabled("session_delta")
    wm.record_widget_disabled("session_delta")
    snapshot = wm.session_snapshot()
    assert snapshot["widgets_disabled"]["radar_awareness"] == 1
    assert snapshot["widgets_disabled"]["session_delta"] == 2


def test_session_snapshot_keys_are_stable(
    recording_posthog: _RecordingPostHog,
) -> None:
    """The shutdown summary log schema is a public-ish contract;
    pin the top-level shape so a rename doesn't silently break
    log-grep workflows."""
    snapshot = wm.session_snapshot()
    assert set(snapshot.keys()) == {"widgets_enabled", "widgets_disabled"}


def test_reset_session_counters_clears_both_dicts(
    recording_posthog: _RecordingPostHog,
) -> None:
    wm.record_widget_enabled("radar_awareness")
    wm.record_widget_disabled("session_delta")
    wm.reset_session_counters()
    snapshot = wm.session_snapshot()
    assert snapshot["widgets_enabled"] == {}
    assert snapshot["widgets_disabled"] == {}
