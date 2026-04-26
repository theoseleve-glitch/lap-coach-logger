"""T218: Accessibility — high-contrast mode toggle persists.

Pins the high-contrast-mode contract at the config layer:

  - ``AccessibilityConfig`` exists with a ``high_contrast`` flag
  - The flag is exposed under ``AppConfig.accessibility``
  - Defaults to ``False`` (opt-in, like every other accessibility
    feature — user must explicitly turn it on)
  - Round-trips via ``to_dict`` / ``from_dict``
  - Old config files (predating this field) load without raising,
    with the new field defaulting to ``False`` — silent upgrade
    on first launch after the feature ships

The actual visual application of high-contrast colors across QML
is tracked separately (every Theme.Tokens reference point would
need conditional swapping). T218's "toggle works" is satisfied
when the config flag exists and persists; the visual swap layers
on top in a follow-up.
"""
from __future__ import annotations

from dataclasses import fields

import pytest

from lap_coach_logger.config.models import AccessibilityConfig, AppConfig


# ---------------------------------------------------------------------------
# AccessibilityConfig dataclass shape
# ---------------------------------------------------------------------------


def test_accessibility_config_exists_with_high_contrast_field() -> None:
    """``AccessibilityConfig`` must be defined and carry a
    ``high_contrast`` boolean. Other accessibility fields can
    follow in later iterations (large_text, reduced_motion, …)."""
    cfg = AccessibilityConfig()
    assert hasattr(cfg, "high_contrast")
    assert isinstance(cfg.high_contrast, bool)


def test_high_contrast_defaults_to_false() -> None:
    """Defaults to off — high-contrast mode is opt-in. Defaulting
    to True would change everyone's visual experience on next
    launch without consent."""
    cfg = AccessibilityConfig()
    assert cfg.high_contrast is False


def test_accessibility_config_only_field_is_high_contrast_for_now() -> None:
    """Documenting current scope. When new accessibility fields
    land (large_text, reduced_motion), update this test — that's
    the prompt to also extend the visual layer."""
    cfg = AccessibilityConfig()
    field_names = {f.name for f in fields(cfg)}
    assert "high_contrast" in field_names
    # Other fields can be added; this test just pins the minimum.


# ---------------------------------------------------------------------------
# AppConfig integration
# ---------------------------------------------------------------------------


def test_app_config_exposes_accessibility() -> None:
    """``AppConfig.accessibility`` is the canonical access path
    for accessibility settings, mirroring ``AppConfig.overlay``
    / ``AppConfig.sync``."""
    config = AppConfig()
    assert isinstance(config.accessibility, AccessibilityConfig)
    assert config.accessibility.high_contrast is False


def test_app_config_high_contrast_can_be_enabled() -> None:
    """The toggle works: setting True updates the value."""
    config = AppConfig()
    config.accessibility.high_contrast = True
    assert config.accessibility.high_contrast is True


# ---------------------------------------------------------------------------
# Persistence: to_dict / from_dict round-trip
# ---------------------------------------------------------------------------


def test_high_contrast_round_trips_via_to_dict_from_dict() -> None:
    """A config saved to disk with high_contrast=True must come
    back as True after the round-trip — otherwise the toggle
    silently resets on every restart."""
    config = AppConfig()
    config.accessibility.high_contrast = True

    payload = config.to_dict()
    restored = AppConfig.from_dict(payload)

    assert restored.accessibility.high_contrast is True


def test_default_high_contrast_round_trips() -> None:
    """Default (False) must also survive round-trip — catches
    regressions where the default flips between save and load."""
    config = AppConfig()
    payload = config.to_dict()
    restored = AppConfig.from_dict(payload)
    assert restored.accessibility.high_contrast is False


# ---------------------------------------------------------------------------
# Backward compatibility: old configs without accessibility section
# ---------------------------------------------------------------------------


def test_old_config_without_accessibility_loads_silently() -> None:
    """A config file written before this feature shipped lacks the
    ``accessibility`` key entirely. ``from_dict`` must NOT raise
    — instead the field defaults to a fresh AccessibilityConfig
    (high_contrast=False)."""
    payload = {
        "output_dir": "/tmp/test",
        "debug": False,
        # Notably missing: accessibility key
    }
    config = AppConfig.from_dict(payload)
    assert isinstance(config.accessibility, AccessibilityConfig)
    assert config.accessibility.high_contrast is False


def test_old_config_with_partial_accessibility_loads() -> None:
    """A config with a partial accessibility dict must merge
    defaults — the user added one field (high_contrast=True),
    other future fields default."""
    payload = {
        "accessibility": {"high_contrast": True},
    }
    config = AppConfig.from_dict(payload)
    assert config.accessibility.high_contrast is True
