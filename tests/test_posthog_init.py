"""T059: ``init_posthog()`` wires the PostHog Python SDK into bootstrap.

T059 ships the SDK readiness only — no events yet (T060 fires the
first ``desktop_app_started`` event). Acceptance is "integrated ⇒
ready": the module-level ``posthog.api_key`` is set when an API key
is configured, and the function no-ops gracefully otherwise.

The contract mirrors ``init_sentry()``:

  * No API key anywhere     -> no-op (False).
  * ``enabled=False``       -> no-op (False).  T065 opt-out plug.
  * posthog missing/broken  -> no-op (False).  Bundle hardening.
  * Otherwise               -> set ``module.api_key``, optionally
                              ``module.host``, return True.

Tests inject a fake posthog module so we never touch the real
network and can introspect attribute writes.
"""
from __future__ import annotations

from typing import Any

import pytest


class _FakePostHog:
    """Mirrors the slice of the ``posthog`` module surface we depend on."""

    def __init__(self) -> None:
        self.api_key: str | None = None
        self.host: str | None = None
        self.capture_calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self.shutdown_called = False
        self.VERSION = "7.13.1-fake"

    def capture(
        self,
        distinct_id: str,
        event: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        self.capture_calls.append((distinct_id, event, properties))

    def shutdown(self) -> None:
        self.shutdown_called = True


@pytest.fixture
def fake_posthog() -> _FakePostHog:
    return _FakePostHog()


# ---------------------------------------------------------------------------
# No-op paths
# ---------------------------------------------------------------------------


def test_init_posthog_returns_false_when_api_key_is_none(
    fake_posthog: _FakePostHog,
) -> None:
    from lap_coach_logger.utils.posthog_init import init_posthog

    result = init_posthog(api_key=None, posthog_module=fake_posthog)

    assert result is False
    assert fake_posthog.api_key is None


def test_init_posthog_returns_false_when_api_key_is_blank(
    fake_posthog: _FakePostHog,
) -> None:
    from lap_coach_logger.utils.posthog_init import init_posthog

    result = init_posthog(api_key="   ", posthog_module=fake_posthog)

    assert result is False
    assert fake_posthog.api_key is None


def test_init_posthog_returns_false_when_disabled(
    fake_posthog: _FakePostHog,
) -> None:
    """T065 opt-out plug: a configured key must NOT bypass user opt-out."""
    from lap_coach_logger.utils.posthog_init import init_posthog

    result = init_posthog(
        api_key="phc_abc123", enabled=False, posthog_module=fake_posthog
    )

    assert result is False
    assert fake_posthog.api_key is None


def test_init_posthog_returns_false_when_module_is_unavailable() -> None:
    """If the bundle ships without ``posthog`` (or the import is
    broken), the helper must NOT crash bootstrap."""
    from types import SimpleNamespace

    from lap_coach_logger.utils.posthog_init import init_posthog

    # Sentinel module without the api_key attr — looks broken to the helper.
    sentinel = SimpleNamespace()

    result = init_posthog(api_key="phc_abc123", posthog_module=sentinel)

    assert result is False


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_init_posthog_sets_api_key_on_module(fake_posthog: _FakePostHog) -> None:
    from lap_coach_logger.utils.posthog_init import init_posthog

    result = init_posthog(api_key="phc_abc123", posthog_module=fake_posthog)

    assert result is True
    assert fake_posthog.api_key == "phc_abc123"


def test_init_posthog_passes_host_when_explicitly_provided(
    fake_posthog: _FakePostHog,
) -> None:
    """Self-hosted instances need the host override; SaaS uses the default."""
    from lap_coach_logger.utils.posthog_init import init_posthog

    init_posthog(
        api_key="phc_abc123",
        host="https://eu.posthog.com",
        posthog_module=fake_posthog,
    )

    assert fake_posthog.host == "https://eu.posthog.com"


def test_init_posthog_leaves_host_untouched_when_omitted(
    fake_posthog: _FakePostHog,
) -> None:
    """The SDK ships with a sane default host — don't write None over it."""
    from lap_coach_logger.utils.posthog_init import init_posthog

    init_posthog(api_key="phc_abc123", posthog_module=fake_posthog)

    assert fake_posthog.host is None  # untouched by helper


# ---------------------------------------------------------------------------
# Env var fallback
# ---------------------------------------------------------------------------


def test_init_posthog_falls_back_to_posthog_api_key_env_var(
    fake_posthog: _FakePostHog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lap_coach_logger.utils.posthog_init import init_posthog

    monkeypatch.setenv("POSTHOG_API_KEY", "phc_env_777")

    result = init_posthog(posthog_module=fake_posthog)

    assert result is True
    assert fake_posthog.api_key == "phc_env_777"


def test_init_posthog_explicit_api_key_wins_over_env_var(
    fake_posthog: _FakePostHog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lap_coach_logger.utils.posthog_init import init_posthog

    monkeypatch.setenv("POSTHOG_API_KEY", "phc_env_777")

    init_posthog(api_key="phc_explicit_999", posthog_module=fake_posthog)

    assert fake_posthog.api_key == "phc_explicit_999"


def test_init_posthog_falls_back_to_posthog_host_env_var(
    fake_posthog: _FakePostHog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lap_coach_logger.utils.posthog_init import init_posthog

    monkeypatch.setenv("POSTHOG_API_KEY", "phc_env_777")
    monkeypatch.setenv("POSTHOG_HOST", "https://self.hosted.local")

    init_posthog(posthog_module=fake_posthog)

    assert fake_posthog.host == "https://self.hosted.local"


def test_init_posthog_no_api_key_anywhere_returns_false(
    fake_posthog: _FakePostHog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lap_coach_logger.utils.posthog_init import init_posthog

    monkeypatch.delenv("POSTHOG_API_KEY", raising=False)

    result = init_posthog(posthog_module=fake_posthog)

    assert result is False
    assert fake_posthog.api_key is None


# ---------------------------------------------------------------------------
# Smoke test: after init, the SDK is "ready" — capture round-trips
# ---------------------------------------------------------------------------


def test_after_init_capture_routes_to_posthog_module(
    fake_posthog: _FakePostHog,
) -> None:
    """T060+ will call ``posthog.capture(distinct_id, event, props)``;
    confirm the seam works once init has set the api_key."""
    from lap_coach_logger.utils.posthog_init import init_posthog

    init_posthog(api_key="phc_abc123", posthog_module=fake_posthog)
    fake_posthog.capture("user-1", "desktop_app_started", {"sim": "iRacing"})

    assert fake_posthog.capture_calls == [
        ("user-1", "desktop_app_started", {"sim": "iRacing"})
    ]
