"""T064: ``ReviewViewModel.notifyInsightViewed`` fires the
``coaching_insight_viewed`` PostHog event.

The coaching presentation layer is partially in place
(``coaching/presentation.py``) but the QML coaching UI hasn't
wired itself to anything yet. T064 ships the **analytics seam** on
the view model so the future coaching cards can call one Qt slot
on visibility / click and the event fires automatically.

Property:

  * ``insight_id`` — stable identifier for the insight being viewed
    (e.g. ``"brake_release_corner_3"``). PostHog funnels need a
    cross-user-comparable string, not a per-session UUID.

Semantics differ from T063 (mode_switched) on purpose:

  * Repeated views of the same insight DO each emit an event.
    PostHog impressions count how often something is seen; three
    glances at an insight is three real events.
  * Empty / blank ``insight_id`` is a no-op — that would mean the
    QML side called us with a missing prop, which is a bug to
    surface in dev (silently dropped), not data to record.

Tests record what reaches ``analytics.track`` via monkeypatch.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def track_recorder(monkeypatch: pytest.MonkeyPatch):
    """Replace ``analytics.track`` with a list-recorder for the test."""
    from lap_coach_logger import analytics

    calls: list[tuple[str, dict]] = []

    def _record(event_name: str, **properties: object) -> None:
        calls.append((event_name, properties))

    monkeypatch.setattr(analytics, "track", _record)
    return calls


def test_notifying_an_insight_view_fires_coaching_insight_viewed(
    track_recorder: list[tuple[str, dict]],
) -> None:
    from lap_coach_logger.viewmodels.review_vm import ReviewViewModel

    vm = ReviewViewModel()

    vm.notifyInsightViewed("brake_release_corner_3")

    events = [c for c in track_recorder if c[0] == "coaching_insight_viewed"]
    assert len(events) == 1
    assert events[0][1]["insight_id"] == "brake_release_corner_3"


def test_blank_or_empty_insight_id_does_not_fire(
    track_recorder: list[tuple[str, dict]],
) -> None:
    """A blank id signals a QML wiring bug — silently drop the event
    rather than polluting the funnel with empty rows."""
    from lap_coach_logger.viewmodels.review_vm import ReviewViewModel

    vm = ReviewViewModel()

    vm.notifyInsightViewed("")
    vm.notifyInsightViewed("   ")

    assert [c for c in track_recorder if c[0] == "coaching_insight_viewed"] == []


def test_repeated_views_of_the_same_insight_emit_one_event_each(
    track_recorder: list[tuple[str, dict]],
) -> None:
    """Each impression is its own event — repeat views matter for funnels."""
    from lap_coach_logger.viewmodels.review_vm import ReviewViewModel

    vm = ReviewViewModel()
    insight = "trail_brake_t1"

    vm.notifyInsightViewed(insight)
    vm.notifyInsightViewed(insight)
    vm.notifyInsightViewed(insight)

    events = [c for c in track_recorder if c[0] == "coaching_insight_viewed"]
    assert [e[1]["insight_id"] for e in events] == [insight, insight, insight]


def test_views_of_different_insights_each_emit_their_own_event(
    track_recorder: list[tuple[str, dict]],
) -> None:
    from lap_coach_logger.viewmodels.review_vm import ReviewViewModel

    vm = ReviewViewModel()

    vm.notifyInsightViewed("brake_release_corner_3")
    vm.notifyInsightViewed("apex_trace_t5")

    events = [c[1]["insight_id"] for c in track_recorder if c[0] == "coaching_insight_viewed"]
    assert events == ["brake_release_corner_3", "apex_trace_t5"]


def test_coaching_insight_viewed_is_safe_when_analytics_unconfigured() -> None:
    """If insights render before bootstrap has wired analytics
    (e.g. in headless tests), the emission must be a no-op."""
    from lap_coach_logger import analytics
    from lap_coach_logger.viewmodels.review_vm import ReviewViewModel

    analytics.reset()
    vm = ReviewViewModel()

    # Must not raise.
    vm.notifyInsightViewed("any_insight_id")
