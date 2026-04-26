"""T224: Telemetry opt-in flow during first-run.

T065 made ``telemetry_enabled`` an opt-OUT switch (defaults
True). T224 changes the contract: telemetry collection is
gated on EXPLICIT first-run consent.

The split:
  - ``telemetry_enabled`` (T065) is the user's preference once
    they've answered the opt-in prompt
  - ``telemetry_consent_given`` (T224) tracks whether the user
    has answered the prompt at all
  - ``telemetry_active`` is the canonical boolean every collector
    checks: True only when consent_given AND enabled

This makes "no consent yet" a distinct state from "consented to
opt out" — both produce zero telemetry, but the first launch
under the new code will trigger the prompt regardless of what
``telemetry_enabled`` says.

Old configs (pre-T224) lack ``telemetry_consent_given``; they
silently load as False so the prompt fires on first launch
after the upgrade. That's the design — pre-T224 we never
actually asked, so consent is not implied.

The visual prompt (a first-run dialog) is follow-up scope; T224
pins the config-layer contract that gates collection.
"""
from __future__ import annotations

from dataclasses import fields

from lap_coach_logger.config.models import AppConfig


# ---------------------------------------------------------------------------
# Field shape
# ---------------------------------------------------------------------------


def test_app_config_has_telemetry_consent_given_field() -> None:
    """The dataclass must carry the consent-tracking field."""
    cfg = AppConfig()
    assert hasattr(cfg, "telemetry_consent_given")
    assert isinstance(cfg.telemetry_consent_given, bool)


def test_telemetry_consent_given_defaults_false() -> None:
    """Defaults to False — explicit consent required. Defaulting
    to True would silently grant consent we never asked for."""
    cfg = AppConfig()
    assert cfg.telemetry_consent_given is False


def test_telemetry_enabled_still_defaults_true() -> None:
    """T065 opt-OUT contract is preserved: ``telemetry_enabled``
    still defaults True. The gate is the AND with consent_given,
    not a default flip on telemetry_enabled (which would force
    every existing user to re-opt-in for no reason)."""
    cfg = AppConfig()
    assert cfg.telemetry_enabled is True


# ---------------------------------------------------------------------------
# telemetry_active property — the canonical gate
# ---------------------------------------------------------------------------


def test_telemetry_active_false_when_no_consent() -> None:
    """No consent → no collection, regardless of enabled flag.
    This is the first-run state."""
    cfg = AppConfig()
    cfg.telemetry_consent_given = False
    cfg.telemetry_enabled = True
    assert cfg.telemetry_active is False


def test_telemetry_active_false_when_consented_but_disabled() -> None:
    """User answered the prompt with No → no collection."""
    cfg = AppConfig()
    cfg.telemetry_consent_given = True
    cfg.telemetry_enabled = False
    assert cfg.telemetry_active is False


def test_telemetry_active_true_only_when_consented_and_enabled() -> None:
    """User answered Yes and hasn't disabled it in settings → collect."""
    cfg = AppConfig()
    cfg.telemetry_consent_given = True
    cfg.telemetry_enabled = True
    assert cfg.telemetry_active is True


def test_telemetry_active_false_when_both_off() -> None:
    """Belt-and-braces: no consent + explicitly disabled → no collection."""
    cfg = AppConfig()
    cfg.telemetry_consent_given = False
    cfg.telemetry_enabled = False
    assert cfg.telemetry_active is False


# ---------------------------------------------------------------------------
# Persistence: to_dict / from_dict round-trip
# ---------------------------------------------------------------------------


def test_consent_given_round_trips_via_to_dict_from_dict() -> None:
    """Once the user answers the prompt, that fact must survive
    a save/load — otherwise the prompt fires every launch."""
    cfg = AppConfig()
    cfg.telemetry_consent_given = True
    cfg.telemetry_enabled = False  # they said No
    payload = cfg.to_dict()
    restored = AppConfig.from_dict(payload)
    assert restored.telemetry_consent_given is True
    assert restored.telemetry_enabled is False
    assert restored.telemetry_active is False


def test_old_config_without_consent_field_loads_as_false() -> None:
    """A config from before T224 lacks ``telemetry_consent_given``.
    It must load with consent_given=False so the user gets
    prompted on first launch under the new code — pre-T224 we
    never asked, so we cannot infer consent."""
    payload = {
        "output_dir": "/tmp/test",
        "telemetry_enabled": True,  # legacy field
        # NOTABLY MISSING: telemetry_consent_given
    }
    cfg = AppConfig.from_dict(payload)
    assert cfg.telemetry_consent_given is False
    assert cfg.telemetry_active is False, (
        "An upgraded user must NOT have telemetry collected "
        "until they answer the consent prompt"
    )


def test_consent_given_listed_in_app_config_fields() -> None:
    """Sanity: the field is part of the AppConfig dataclass
    (so dataclasses.asdict picks it up correctly)."""
    field_names = {f.name for f in fields(AppConfig)}
    assert "telemetry_consent_given" in field_names


# ---------------------------------------------------------------------------
# Bootstrap-level integration: bootstrap reads telemetry_active
# ---------------------------------------------------------------------------


def test_bootstrap_uses_telemetry_active_not_just_enabled() -> None:
    """Drift-prevention: bootstrap.py must gate Sentry/PostHog
    init on ``config.telemetry_active`` (the AND gate), not on
    ``config.telemetry_enabled`` alone — otherwise first-run
    users get telemetry without consenting."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    bootstrap_src = (
        repo_root / "src" / "lap_coach_logger" / "bootstrap.py"
    ).read_text(encoding="utf-8")

    assert "telemetry_active" in bootstrap_src, (
        "bootstrap.py does not reference telemetry_active — it "
        "must use the consent-aware gate, not telemetry_enabled "
        "alone, otherwise first-run users get telemetry without "
        "consenting"
    )
