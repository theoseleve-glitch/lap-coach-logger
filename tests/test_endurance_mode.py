"""T109: ``EnduranceMode`` — long-run focus, stint awareness.

Endurance sessions (1h+: 6h Le Mans Virtual, MX-5 endurance,
team enduros) are paced races where consistency over many laps
matters more than peak speed. Coaching cadence is "minimal"
(don't fatigue the driver) but strategy is conservative —
fuel margin needs headroom for an unexpected long stint or a
botched pit stop.
"""
from __future__ import annotations

from lap_coach_logger.core.modes import Mode
from lap_coach_logger.core.modes.endurance import EnduranceMode


def test_endurance_mode_is_a_concrete_mode_subclass() -> None:
    assert issubclass(EnduranceMode, Mode)


def test_endurance_mode_can_be_instantiated() -> None:
    EnduranceMode()


def test_endurance_mode_has_endurance_id() -> None:
    assert EnduranceMode().id == "endurance"


def test_endurance_mode_display_name_is_endurance() -> None:
    assert EnduranceMode().name == "Endurance"


def test_endurance_mode_coaching_is_minimal_to_avoid_fatigue() -> None:
    """Long-format racing means hours of focus. Verbose coaching
    over 4+ hours actively harms the driver — every audio cue
    becomes a distraction. Match Sprint's "minimal" rather than
    Practice's "verbose"."""
    assert EnduranceMode().coaching_verbosity == "minimal"


def test_endurance_mode_binds_endurance_overlay_preset() -> None:
    """T124 ships the "endurance" preset — 10 widgets including
    stint timer, tire life, long-run pace."""
    assert EnduranceMode().overlay_preset_id == "endurance"


def test_endurance_mode_environment_tag_is_sim_endurance() -> None:
    assert EnduranceMode().environment_tag == "sim_endurance"


def test_endurance_mode_strategy_safety_margin_is_higher_than_sprint() -> None:
    """Long stints accumulate uncertainty (tire deg, fuel
    consumption variance, traffic). The margin must be larger
    than Sprint's 5% — typical endurance pit-strategy uses
    10-15% headroom on fuel projections so an unplanned slow
    sector or a Code-60 cycle doesn't strand the car. Pinning
    a *range* (not a single value) catches an off-by-zero
    while still letting future calibration tune the exact
    figure."""
    margin = EnduranceMode().strategy_safety_margin
    assert 0.05 < margin <= 0.20


def test_endurance_safety_margin_is_strictly_greater_than_sprint() -> None:
    """Cross-mode invariant: endurance MUST pad more than
    sprint. If a refactor accidentally swapped the two
    constants, races would lose pace and endurance would DNF.
    Pin the relative ordering as a regression guard."""
    from lap_coach_logger.core.modes.sprint import SprintMode

    assert (
        EnduranceMode().strategy_safety_margin
        > SprintMode().strategy_safety_margin
    )
