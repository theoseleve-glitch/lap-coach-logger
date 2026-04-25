"""T108: ``SprintMode`` — race coaching, simplified strategy.

Sprint races (15-30 minute formats: weekly leagues, MX-5 cups,
GT iRacing series) emphasise consistency over the few laps
that decide the result. Coaching must NOT distract — minimal
verbosity, only the highest-priority insights surface. Strategy
is simplified: typically no pit stop, fuel margin tight.
"""
from __future__ import annotations

from lap_coach_logger.core.modes import Mode
from lap_coach_logger.core.modes.sprint import SprintMode


def test_sprint_mode_is_a_concrete_mode_subclass() -> None:
    assert issubclass(SprintMode, Mode)


def test_sprint_mode_can_be_instantiated() -> None:
    SprintMode()


def test_sprint_mode_has_sprint_id() -> None:
    """Settings persistence (T117) keys on this exact value."""
    assert SprintMode().id == "sprint"


def test_sprint_mode_display_name_is_sprint() -> None:
    assert SprintMode().name == "Sprint"


def test_sprint_mode_coaching_is_minimal() -> None:
    """Race mode = "shut up unless it's important". Verbose
    coaching during a 15-min race would actively harm the
    driver's focus on race-craft. Pinning verbatim catches a
    refactor that would silently flip this to ``"verbose"``."""
    assert SprintMode().coaching_verbosity == "minimal"


def test_sprint_mode_binds_race_minimal_overlay_preset() -> None:
    """T122 ships the "race-minimal" preset — 8-10 core widgets
    (lap delta, fuel, tires, coach, position, flags, sector
    color, gap). Sprint mode binds to that."""
    assert SprintMode().overlay_preset_id == "race-minimal"


def test_sprint_mode_environment_tag_is_sim_sprint() -> None:
    assert SprintMode().environment_tag == "sim_sprint"


def test_sprint_mode_strategy_safety_margin_is_low() -> None:
    """A short race ⇒ fuel-burn confidence is high (only a few
    laps to project), pit stop probably not needed. Margin
    should be small but non-zero (a 0.05 / 5% margin lets the
    fuel calc round up safely without padding to "go save 3
    laps' worth of fuel"). 0.0 would be too aggressive (one
    bad in-lap and you DNF); 0.20+ would be too conservative
    (lose time managing fuel that wasn't going to run out)."""
    margin = SprintMode().strategy_safety_margin
    assert 0.0 < margin < 0.20
