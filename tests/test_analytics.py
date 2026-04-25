"""T060: ``analytics.track()`` fires PostHog events safely.

T060 introduces the first product-analytics event
(``desktop_app_started``). T061–T064 follow the same pattern: a
one-line ``analytics.track("event_name", **props)`` call. This file
covers the **dispatch contract** of that helper plus the persistent
installation-ID helper that supplies PostHog's required
``distinct_id`` for events that fire before any user has paired.

Key invariants:

* ``track()`` is **always safe to call** — before configure, when
  PostHog is disabled, when posthog isn't installed, when the SDK
  raises. Analytics are advisory, never load-bearing.
* ``configure()`` is idempotent and resettable (so tests can hand
  the module a fresh fake between cases).
* ``get_or_create_install_id()`` returns the **same** UUID across
  restarts so longitudinal funnels work.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest


class _FakePostHog:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.capture_should_raise: Exception | None = None

    def capture(
        self,
        distinct_id: str,
        event: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        if self.capture_should_raise is not None:
            raise self.capture_should_raise
        self.calls.append(
            {"distinct_id": distinct_id, "event": event, "properties": properties}
        )


@pytest.fixture
def fake_posthog() -> _FakePostHog:
    return _FakePostHog()


@pytest.fixture(autouse=True)
def _reset_analytics_module() -> None:
    """Each test starts with a clean (un-configured) analytics module."""
    from lap_coach_logger import analytics

    analytics.reset()
    yield
    analytics.reset()


# ---------------------------------------------------------------------------
# track() safety: must never raise, regardless of state
# ---------------------------------------------------------------------------


def test_track_is_a_safe_noop_before_configure() -> None:
    from lap_coach_logger import analytics

    # Must not raise.
    analytics.track("desktop_app_started")


def test_track_is_a_safe_noop_when_disabled(fake_posthog: _FakePostHog) -> None:
    from lap_coach_logger import analytics

    analytics.configure(
        posthog_module=fake_posthog, distinct_id="u-1", enabled=False
    )
    analytics.track("desktop_app_started")

    assert fake_posthog.calls == []


def test_track_is_a_safe_noop_when_posthog_module_missing() -> None:
    from lap_coach_logger import analytics

    analytics.configure(posthog_module=None, distinct_id="u-1", enabled=True)
    analytics.track("desktop_app_started")
    # No exception, nothing to assert beyond not crashing.


def test_track_swallows_capture_exceptions(fake_posthog: _FakePostHog) -> None:
    """Network blip mid-capture must NOT crash the app."""
    from lap_coach_logger import analytics

    fake_posthog.capture_should_raise = RuntimeError("network down")
    analytics.configure(
        posthog_module=fake_posthog, distinct_id="u-1", enabled=True
    )

    # Must not raise.
    analytics.track("desktop_app_started")


# ---------------------------------------------------------------------------
# track() happy path: dispatches to posthog.capture with right args
# ---------------------------------------------------------------------------


def test_track_dispatches_event_to_configured_posthog(
    fake_posthog: _FakePostHog,
) -> None:
    from lap_coach_logger import analytics

    analytics.configure(
        posthog_module=fake_posthog, distinct_id="install-abc", enabled=True
    )
    analytics.track("desktop_app_started")

    assert fake_posthog.calls == [
        {
            "distinct_id": "install-abc",
            "event": "desktop_app_started",
            "properties": {},
        }
    ]


def test_track_forwards_arbitrary_properties(fake_posthog: _FakePostHog) -> None:
    from lap_coach_logger import analytics

    analytics.configure(
        posthog_module=fake_posthog, distinct_id="install-abc", enabled=True
    )
    analytics.track(
        "desktop_app_started",
        version="2.0.0",
        build_kind="development",
        platform="win32",
    )

    call = fake_posthog.calls[0]
    assert call["properties"] == {
        "version": "2.0.0",
        "build_kind": "development",
        "platform": "win32",
    }


def test_track_can_fire_multiple_events_after_one_configure(
    fake_posthog: _FakePostHog,
) -> None:
    from lap_coach_logger import analytics

    analytics.configure(
        posthog_module=fake_posthog, distinct_id="u-1", enabled=True
    )
    analytics.track("desktop_app_started")
    analytics.track("session_captured", sim="iRacing")

    assert [c["event"] for c in fake_posthog.calls] == [
        "desktop_app_started",
        "session_captured",
    ]


# ---------------------------------------------------------------------------
# reconfigure: tests + future "user paired" hook need to swap distinct_id
# ---------------------------------------------------------------------------


def test_configure_can_be_called_again_to_swap_distinct_id(
    fake_posthog: _FakePostHog,
) -> None:
    """After Clerk pairing the wiring may rewire distinct_id from
    install-id to the user's account email — re-configure must take."""
    from lap_coach_logger import analytics

    analytics.configure(
        posthog_module=fake_posthog, distinct_id="install-abc", enabled=True
    )
    analytics.configure(
        posthog_module=fake_posthog,
        distinct_id="user@example.com",
        enabled=True,
    )
    analytics.track("desktop_app_started")

    assert fake_posthog.calls[0]["distinct_id"] == "user@example.com"


# ---------------------------------------------------------------------------
# get_or_create_install_id: stable per-installation UUID
# ---------------------------------------------------------------------------


def test_get_or_create_install_id_creates_uuid_on_first_call(
    tmp_path: Path,
) -> None:
    from lap_coach_logger.analytics import get_or_create_install_id

    state_path = tmp_path / "install_id.json"
    install_id = get_or_create_install_id(state_path)

    # Format: must parse as a UUID.
    UUID(install_id)
    assert state_path.exists()


def test_get_or_create_install_id_returns_same_value_across_calls(
    tmp_path: Path,
) -> None:
    """Longitudinal funnels in PostHog need the SAME id across every
    app launch on this machine."""
    from lap_coach_logger.analytics import get_or_create_install_id

    state_path = tmp_path / "install_id.json"
    first = get_or_create_install_id(state_path)
    second = get_or_create_install_id(state_path)

    assert first == second


def test_get_or_create_install_id_recovers_from_corrupt_file(
    tmp_path: Path,
) -> None:
    """A garbled file (e.g. crashed write) must NOT crash bootstrap;
    the helper falls back to issuing a fresh UUID."""
    from lap_coach_logger.analytics import get_or_create_install_id

    state_path = tmp_path / "install_id.json"
    state_path.write_text("{not valid json", encoding="utf-8")

    install_id = get_or_create_install_id(state_path)
    UUID(install_id)


def test_get_or_create_install_id_persists_human_readable_json(
    tmp_path: Path,
) -> None:
    """For support: a user should be able to open the file and see what's there."""
    from lap_coach_logger.analytics import get_or_create_install_id

    state_path = tmp_path / "install_id.json"
    install_id = get_or_create_install_id(state_path)

    parsed = json.loads(state_path.read_text(encoding="utf-8"))
    assert parsed == {"install_id": install_id}
