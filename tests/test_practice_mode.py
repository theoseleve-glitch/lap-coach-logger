"""T107: ``PracticeMode`` — verbose coaching, minimal strategy.

Practice sessions are where drivers want **everything**: every
late-brake, every apex slip, every consistency wobble. Strategy
is irrelevant (no fuel pressure, no race-craft trade-offs), so
the safety margin can be zero — the user is here to learn, not
to manage risk.

Bindings:
- coaching_verbosity = "verbose" (every fired rule reaches the
  card, no extra gating beyond T088 / T092)
- overlay_preset_id = "practice" (T123 — 12 widgets including
  inputs, g-g, live trace)
- environment_tag = "sim_practice" (T115 — server aggregates
  practice sessions separately)
- strategy_safety_margin = 0.0 (no fuel/time padding)
"""
from __future__ import annotations

from lap_coach_logger.core.modes import Mode
from lap_coach_logger.core.modes.practice import PracticeMode


def test_practice_mode_is_a_concrete_mode_subclass() -> None:
    """Subclass relationship is the load-bearing structural
    contract — without it ModeEngine (T111) won't accept
    PracticeMode in its registry."""
    assert issubclass(PracticeMode, Mode)


def test_practice_mode_can_be_instantiated() -> None:
    """All six abstract members declared, so Python's ABC
    machinery lets us instantiate. A typo on any class-level
    constant would surface here as an ABC TypeError."""
    PracticeMode()  # must not raise


def test_practice_mode_has_practice_id() -> None:
    """``id`` is the serialization key — settings persistence
    (T117) keys on this exact value. Pinning verbatim prevents
    a refactor from breaking saved-mode load."""
    assert PracticeMode().id == "practice"


def test_practice_mode_display_name_is_practice() -> None:
    """User-facing label — pinned so a copy-editor's
    "Free Practice" or "Practice Mode" rename doesn't sneak
    through unnoticed."""
    assert PracticeMode().name == "Practice"


def test_practice_mode_coaching_is_verbose() -> None:
    """Practice = "tell me everything". A "minimal" or "off"
    setting here would silently undermine the whole reason
    a driver picks practice mode in the first place."""
    assert PracticeMode().coaching_verbosity == "verbose"


def test_practice_mode_binds_practice_overlay_preset() -> None:
    """T112 maps mode → preset id. T123 ships the "practice"
    preset (12 widgets including inputs, g-g, live trace)."""
    assert PracticeMode().overlay_preset_id == "practice"


def test_practice_mode_environment_tag_is_sim_practice() -> None:
    """T115 stamps this on the finalize bundle so the server
    can aggregate practice sessions separately. The
    ``"sim_"`` prefix mirrors the convention from
    DT-014's acceptance criteria."""
    assert PracticeMode().environment_tag == "sim_practice"


def test_practice_mode_strategy_safety_margin_is_zero() -> None:
    """No fuel pressure, no race-craft trade-offs ⇒ no padding.
    A non-zero margin here would suppress otherwise-actionable
    coaching about fuel-burn drills, which is part of practice."""
    assert PracticeMode().strategy_safety_margin == 0.0


def test_practice_mode_is_stateless_and_singleton_safe() -> None:
    """Two instances must be interchangeable — class-level
    constants only, no instance state. T111's ModeEngine
    instantiates once and shares; that requires this property."""
    a = PracticeMode()
    b = PracticeMode()
    assert a.id == b.id
    assert a.coaching_verbosity == b.coaching_verbosity
    assert a.overlay_preset_id == b.overlay_preset_id
