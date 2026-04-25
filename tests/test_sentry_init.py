"""T056: ``init_sentry()`` wires the Sentry Python SDK into bootstrap.

The acceptance is "500 error reports": once the desktop boots,
unhandled exceptions land in Sentry. The SDK supplies the actual
capture/send machinery — our concern is the **initialization
contract**: when to init, when to no-op, and what tags to apply.

The fragile path is "Sentry init runs in CI / dev / opt-out builds
and tries to send events the user never agreed to." So the contract:

  * No DSN configured -> no-op (returns ``False``).
  * Explicit ``enabled=False`` -> no-op (T065 opt-out plug).
  * sentry-sdk missing or broken -> no-op (bundle hardening).
  * Otherwise -> call ``sentry_sdk.init`` with DSN + optional
    ``environment`` / ``release`` tags and return ``True``.

Tests inject a fake sentry-sdk module so we never touch the real
network and can introspect what was passed.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


class _FakeSentry:
    """Mimics the slice of the ``sentry_sdk`` module surface we depend on."""

    def __init__(self) -> None:
        self.init_calls: list[dict[str, Any]] = []
        self.capture_calls: list[BaseException] = []
        self.VERSION = "2.58.0-fake"

    def init(self, **kwargs: Any) -> None:
        self.init_calls.append(kwargs)

    def capture_exception(self, exc: BaseException) -> None:
        self.capture_calls.append(exc)


@pytest.fixture
def fake_sentry() -> _FakeSentry:
    return _FakeSentry()


# ---------------------------------------------------------------------------
# No-op paths
# ---------------------------------------------------------------------------


def test_init_sentry_returns_false_when_dsn_is_none(fake_sentry: _FakeSentry) -> None:
    from lap_coach_logger.utils.sentry_init import init_sentry

    result = init_sentry(dsn=None, sentry_module=fake_sentry)

    assert result is False
    assert fake_sentry.init_calls == []


def test_init_sentry_returns_false_when_dsn_is_empty_string(
    fake_sentry: _FakeSentry,
) -> None:
    from lap_coach_logger.utils.sentry_init import init_sentry

    result = init_sentry(dsn="   ", sentry_module=fake_sentry)

    assert result is False
    assert fake_sentry.init_calls == []


def test_init_sentry_returns_false_when_disabled(fake_sentry: _FakeSentry) -> None:
    """T065 opt-out plug: a user-disabled telemetry flag must short-
    circuit even when a DSN is present."""
    from lap_coach_logger.utils.sentry_init import init_sentry

    result = init_sentry(
        dsn="https://abc@example.ingest.sentry.io/123",
        enabled=False,
        sentry_module=fake_sentry,
    )

    assert result is False
    assert fake_sentry.init_calls == []


def test_init_sentry_returns_false_when_sentry_sdk_unavailable() -> None:
    """If the bundle ships without sentry-sdk (or the import blows up
    for some reason), init_sentry must NOT crash the app — it returns
    False and the rest of bootstrap continues."""
    from lap_coach_logger.utils.sentry_init import init_sentry

    sentinel = SimpleNamespace()  # no .init attribute → broken module

    result = init_sentry(
        dsn="https://abc@example.ingest.sentry.io/123",
        sentry_module=sentinel,
    )

    assert result is False


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_init_sentry_calls_sentry_init_with_dsn(fake_sentry: _FakeSentry) -> None:
    from lap_coach_logger.utils.sentry_init import init_sentry

    result = init_sentry(
        dsn="https://abc@example.ingest.sentry.io/123",
        sentry_module=fake_sentry,
    )

    assert result is True
    assert len(fake_sentry.init_calls) == 1
    assert (
        fake_sentry.init_calls[0]["dsn"]
        == "https://abc@example.ingest.sentry.io/123"
    )


def test_init_sentry_passes_environment_and_release_tags(
    fake_sentry: _FakeSentry,
) -> None:
    """Tag plumbing now means T058 (release tagging) is a one-liner."""
    from lap_coach_logger.utils.sentry_init import init_sentry

    init_sentry(
        dsn="https://abc@example.ingest.sentry.io/123",
        environment="production",
        release="lap-coach-logger@2.0.0",
        sentry_module=fake_sentry,
    )

    assert fake_sentry.init_calls[0]["environment"] == "production"
    assert fake_sentry.init_calls[0]["release"] == "lap-coach-logger@2.0.0"


def test_init_sentry_omits_unset_tags(fake_sentry: _FakeSentry) -> None:
    """Don't pass ``environment=None`` / ``release=None`` — Sentry
    treats an explicit ``None`` differently from "not specified"."""
    from lap_coach_logger.utils.sentry_init import init_sentry

    init_sentry(
        dsn="https://abc@example.ingest.sentry.io/123",
        sentry_module=fake_sentry,
    )

    call = fake_sentry.init_calls[0]
    assert "environment" not in call
    assert "release" not in call


# ---------------------------------------------------------------------------
# Env var fallback (production wiring will read SENTRY_DSN at startup)
# ---------------------------------------------------------------------------


def test_init_sentry_falls_back_to_sentry_dsn_env_var(
    fake_sentry: _FakeSentry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lap_coach_logger.utils.sentry_init import init_sentry

    monkeypatch.setenv("SENTRY_DSN", "https://env@example.ingest.sentry.io/777")

    result = init_sentry(sentry_module=fake_sentry)

    assert result is True
    assert (
        fake_sentry.init_calls[0]["dsn"]
        == "https://env@example.ingest.sentry.io/777"
    )


def test_init_sentry_explicit_dsn_wins_over_env_var(
    fake_sentry: _FakeSentry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caller intent beats environment — useful for tests + multi-env wiring."""
    from lap_coach_logger.utils.sentry_init import init_sentry

    monkeypatch.setenv("SENTRY_DSN", "https://env@example.ingest.sentry.io/777")

    init_sentry(
        dsn="https://explicit@example.ingest.sentry.io/999",
        sentry_module=fake_sentry,
    )

    assert (
        fake_sentry.init_calls[0]["dsn"]
        == "https://explicit@example.ingest.sentry.io/999"
    )


def test_init_sentry_no_dsn_anywhere_returns_false(
    fake_sentry: _FakeSentry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lap_coach_logger.utils.sentry_init import init_sentry

    monkeypatch.delenv("SENTRY_DSN", raising=False)

    result = init_sentry(sentry_module=fake_sentry)

    assert result is False
    assert fake_sentry.init_calls == []


# ---------------------------------------------------------------------------
# Smoke test: after init, capture_exception works (sanity check on the seam)
# ---------------------------------------------------------------------------


def test_after_init_capture_exception_routes_to_sentry(
    fake_sentry: _FakeSentry,
) -> None:
    """Once init_sentry has run, an unhandled exception captured via
    the SDK module reaches sentry_sdk.capture_exception."""
    from lap_coach_logger.utils.sentry_init import init_sentry

    init_sentry(
        dsn="https://abc@example.ingest.sentry.io/123",
        sentry_module=fake_sentry,
    )
    err = RuntimeError("smoke")
    fake_sentry.capture_exception(err)

    assert fake_sentry.capture_calls == [err]


# ---------------------------------------------------------------------------
# T058: sentry_release_tag — <package>@<version> for Sentry "Releases"
# ---------------------------------------------------------------------------


def test_sentry_release_tag_uses_recommended_package_at_version_format() -> None:
    from lap_coach_logger.utils.sentry_init import sentry_release_tag

    assert sentry_release_tag(version="9.9.9") == "lap-coach-logger@9.9.9"


def test_sentry_release_tag_default_pulls_live_package_version() -> None:
    """When no explicit version is passed, the helper reads
    ``lap_coach_logger.__version__`` so a version bump in
    ``app_identity.py`` flows automatically into the Sentry release
    tag without a second edit."""
    from lap_coach_logger import __version__
    from lap_coach_logger.utils.sentry_init import sentry_release_tag

    assert sentry_release_tag() == f"lap-coach-logger@{__version__}"


def test_init_sentry_with_release_tag_helper_round_trips_to_sdk(
    fake_sentry: _FakeSentry,
) -> None:
    """The bootstrap will call ``init_sentry(release=sentry_release_tag())``
    so make sure the resulting kwarg reaches the SDK as-is."""
    from lap_coach_logger.utils.sentry_init import init_sentry, sentry_release_tag

    init_sentry(
        dsn="https://abc@example.ingest.sentry.io/123",
        release=sentry_release_tag(version="2.0.0"),
        sentry_module=fake_sentry,
    )

    assert fake_sentry.init_calls[0]["release"] == "lap-coach-logger@2.0.0"
