"""T126: Default preset on first install is ``race-minimal``.

On a clean install, before the user has ever picked a mode or
saved a preference, the desktop has to *display something* —
T126 pins that "something" as the ``race-minimal`` preset (T122).

Reasoning:
- Most users land on the desktop *during* a session, not before.
- A race session is the most common entry point (sprint cups,
  weekly leagues), so race-minimal serves the median user without
  drowning newcomers in practice/endurance widget density.
- race-minimal is the smallest validated preset (8 widgets) — if
  a user wants more they upgrade by switching modes; if they want
  less they hide widgets manually. The default leans *under-*
  cluttered rather than over-cluttered.

This is independent of:
- Mode persistence (T117 — that's about *re-restart* recall, not
  first install).
- Auto-detect (T118 — that's a *hint* layered on top of the
  default once the sim is running and the session type is known).

Pure deliverable: a tested constant + helper. Caller invokes
``default_preset_id_on_first_install()`` whenever it's bootstrapping
a fresh session profile and has no other signal.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------


def test_default_preset_on_first_install_is_race_minimal() -> None:
    """T126 headline: the preset id reported as the first-install
    default must be ``"race-minimal"``. A future regression that
    quietly switches it to ``"practice"`` (verbose layout that
    overwhelms newcomers) gets caught here."""
    from lap_coach_logger.core.modes.builtin_presets import (
        default_preset_id_on_first_install,
    )

    assert default_preset_id_on_first_install() == "race-minimal"


def test_default_preset_id_resolves_to_a_real_preset() -> None:
    """Cross-check: the id reported by the helper must round-trip
    through ``get_builtin_preset`` to a real ModeOverlayPreset.
    Catches a refactor that changes the constant string but
    forgets to ship a matching preset (would crash the bootstrap
    on first install)."""
    from lap_coach_logger.core.modes.builtin_presets import (
        default_preset_id_on_first_install,
        get_builtin_preset,
    )

    preset_id = default_preset_id_on_first_install()
    preset = get_builtin_preset(preset_id)

    assert preset is not None
    assert preset.preset_id == preset_id


def test_default_first_install_preset_is_race_minimal_constant() -> None:
    """Pin the helper return to the actual ``RACE_MINIMAL_PRESET``
    instance — guarantees the bootstrap path uses the canonical
    object (same instance, same widgets, same positions) rather
    than a separately-built copy."""
    from lap_coach_logger.core.modes.builtin_presets import (
        RACE_MINIMAL_PRESET,
        default_preset_id_on_first_install,
        get_builtin_preset,
    )

    assert get_builtin_preset(default_preset_id_on_first_install()) is RACE_MINIMAL_PRESET
