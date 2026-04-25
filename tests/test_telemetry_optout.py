"""T065: ``AppConfig.telemetry_enabled`` flag is respected end-to-end.

Defaulting to ``True`` matches Sentry/PostHog conventions: telemetry
is on by default, users opt OUT, not in. Old config files that
predate this field load as ``True`` via :meth:`AppConfig.from_dict`
so the upgrade is silent.

The "respected" claim is established by composition:

* :func:`utils.sentry_init.init_sentry` returns ``False`` (no SDK
  init) when ``enabled=False`` — already verified in T056.
* :func:`utils.posthog_init.init_posthog` returns ``False`` (no
  api_key set) when ``enabled=False`` — already verified in T059.
* :mod:`analytics` is in safe-noop mode when configured with
  ``enabled=False`` — already verified in T060.

T065's specific contribution is the **plumbing** that lets one
user-facing toggle disable all three at once. Tests below verify
the flag round-trips cleanly through config persistence and that
when bootstrap passes ``enabled=cfg.telemetry_enabled=False`` to
the init functions, every provider stays off.
"""
from __future__ import annotations

from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Config field round-trip
# ---------------------------------------------------------------------------


def test_telemetry_enabled_defaults_to_true_on_fresh_config() -> None:
    """Brand-new config (no file on disk) => telemetry is on."""
    from lap_coach_logger.config.models import AppConfig

    cfg = AppConfig()

    assert cfg.telemetry_enabled is True


def test_telemetry_enabled_roundtrips_through_to_dict_from_dict() -> None:
    from lap_coach_logger.config.models import AppConfig

    cfg = AppConfig()
    cfg.telemetry_enabled = False
    blob = cfg.to_dict()
    restored = AppConfig.from_dict(blob)

    assert restored.telemetry_enabled is False


def test_legacy_config_dict_without_field_defaults_to_true() -> None:
    """Existing user configs that predate the field must load as True."""
    from lap_coach_logger.config.models import AppConfig

    legacy = {"output_dir": "/tmp/sessions", "debug": False}

    cfg = AppConfig.from_dict(legacy)

    assert cfg.telemetry_enabled is True


# ---------------------------------------------------------------------------
# End-to-end "respected": disabled flag => no provider initializes
# ---------------------------------------------------------------------------


class _FakeSentry:
    def __init__(self) -> None:
        self.init_calls: list[dict[str, Any]] = []

    def init(self, **kwargs: Any) -> None:
        self.init_calls.append(kwargs)


class _FakePostHog:
    def __init__(self) -> None:
        self.api_key: str | None = None
        self.host: str | None = None


def test_telemetry_disabled_keeps_sentry_uninitialized_even_with_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User opt-out beats configured DSN — no events leak to Sentry."""
    from lap_coach_logger.config.models import AppConfig
    from lap_coach_logger.utils.sentry_init import init_sentry

    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    cfg = AppConfig()
    cfg.telemetry_enabled = False
    fake_sentry = _FakeSentry()

    active = init_sentry(
        enabled=cfg.telemetry_enabled, sentry_module=fake_sentry
    )

    assert active is False
    assert fake_sentry.init_calls == []


def test_telemetry_disabled_keeps_posthog_uninitialized_even_with_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User opt-out beats configured API key — no events leak to PostHog."""
    from lap_coach_logger.config.models import AppConfig
    from lap_coach_logger.utils.posthog_init import init_posthog

    monkeypatch.setenv("POSTHOG_API_KEY", "phc_abc")
    cfg = AppConfig()
    cfg.telemetry_enabled = False
    fake_posthog = _FakePostHog()

    active = init_posthog(
        enabled=cfg.telemetry_enabled, posthog_module=fake_posthog
    )

    assert active is False
    assert fake_posthog.api_key is None


def test_telemetry_enabled_default_true_initializes_when_dsn_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default-on path is still functional (regression guard for the
    plumbing — ``enabled=True`` must not block initialization)."""
    from lap_coach_logger.config.models import AppConfig
    from lap_coach_logger.utils.sentry_init import init_sentry

    cfg = AppConfig()  # default telemetry_enabled=True
    fake_sentry = _FakeSentry()

    active = init_sentry(
        dsn="https://abc@example.com/1",
        enabled=cfg.telemetry_enabled,
        sentry_module=fake_sentry,
    )

    assert active is True
    assert len(fake_sentry.init_calls) == 1
