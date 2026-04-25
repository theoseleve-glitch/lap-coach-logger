"""T142: Pit-armed audio cue.

Per the spec marker "⇒ optional", the audio cue is opt-in via
constructor injection — the same pattern :class:`CoachingCardVM`
uses for T096's voice cues:

- ``pit_arm_audio_player: Callable[[], None] | None``
- ``None`` (default) → silent. Bootstrap may pass a real player
  closure or leave it None depending on the user's
  ``Enable voice cues`` setting; both are valid configurations.

Trigger contract: fire on the *transition* into armed
(``pitArmed`` going False → True). Don't fire on:

- the disarm transition (the cue is for "arm-up your pit lap",
  not "stand down"),
- repeated armed snapshots (auto-recalc runs every lap; the
  cue must not nag),
- a no-op recalc that leaves the state unchanged.
"""
from __future__ import annotations

from tests.qt_mock import install
install()

from lap_coach_logger.viewmodels.overlay_vm import OverlayViewModel  # noqa: E402


def _vm_with_recorder() -> tuple[OverlayViewModel, list[None]]:
    """Build an OverlayViewModel with a list-append audio player —
    the standard test-harness shape for the optional cue."""
    plays: list[None] = []
    vm = OverlayViewModel()
    vm._pit_arm_audio_player = lambda: plays.append(None)  # type: ignore[attr-defined]
    return vm, plays


# ---------------------------------------------------------------------------
# Default: no audio player → silent (don't crash)
# ---------------------------------------------------------------------------


def test_default_construction_has_no_audio_player() -> None:
    """Bootstrap may not configure a player. The VM must
    tolerate the absence — no crash, no fire — even when an
    arm transition happens."""
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)

    vm._lap_number = 15
    vm._fuel_level = 2.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()  # transition to armed; no player

    assert vm.pitArmed is True  # confirm transition happened


# ---------------------------------------------------------------------------
# Player fires on transition to armed
# ---------------------------------------------------------------------------


def test_audio_cue_fires_on_transition_to_armed() -> None:
    """The headline contract: when pitArmed flips False → True
    the audio player gets called once. Any pit cue is the
    user's earliest sensory alert that the threshold's been
    crossed — silence here defeats the feature."""
    vm, plays = _vm_with_recorder()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)

    vm._lap_number = 15
    vm._fuel_level = 2.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is True
    assert len(plays) == 1


# ---------------------------------------------------------------------------
# Player does NOT fire on transition to disarmed
# ---------------------------------------------------------------------------


def test_audio_cue_does_not_fire_on_transition_to_disarmed() -> None:
    """The cue is for "arm up", not "stand down". An automated
    disarm (e.g., after refuelling) must not play the same
    sound — that would be confusing in races where conditions
    fluctuate around the threshold."""
    vm, plays = _vm_with_recorder()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)
    # Establish armed
    vm._lap_number = 15
    vm._fuel_level = 2.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()
    assert vm.pitArmed is True
    plays.clear()

    # Healthy snapshot → disarm
    vm._lap_number = 16
    vm._fuel_level = 60.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is False
    assert plays == []


# ---------------------------------------------------------------------------
# Player does NOT fire on subsequent armed-stable recalcs
# ---------------------------------------------------------------------------


def test_audio_cue_does_not_repeat_while_armed_state_persists() -> None:
    """Auto-recalc runs every lap. If the threshold stays
    crossed across multiple laps the cue must NOT play on
    every recalc — once per arm event, not once per lap."""
    vm, plays = _vm_with_recorder()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)

    # First arm
    vm._lap_number = 15
    vm._fuel_level = 2.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()
    assert len(plays) == 1

    # Same critical state, next lap — no second cue
    vm._lap_number = 16
    vm._fuel_level = 1.0  # still critical, still armed
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is True
    assert len(plays) == 1


# ---------------------------------------------------------------------------
# Player does NOT fire on no-op (state unchanged from disarmed)
# ---------------------------------------------------------------------------


def test_audio_cue_does_not_fire_on_disarmed_no_op_recalcs() -> None:
    """Healthy state recalc → state stays False → no cue. Pin
    this so a regression doesn't accidentally fire on every
    snapshot when nothing has changed."""
    vm, plays = _vm_with_recorder()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)

    vm._lap_number = 5
    vm._fuel_level = 50.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()
    vm._lap_number = 6
    vm.recalculateLiveStrategy()
    vm._lap_number = 7
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is False
    assert plays == []


# ---------------------------------------------------------------------------
# Re-arming after a disarm DOES fire again
# ---------------------------------------------------------------------------


def test_audio_cue_fires_again_on_re_arm_after_disarm() -> None:
    """After a full arm/disarm cycle, a fresh arm transition
    is a new event — cue fires. Models the realistic flow:
    fuel runs low (arm), pit + refuel (disarm), tires wear
    down later (re-arm)."""
    vm, plays = _vm_with_recorder()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)

    # Arm
    vm._lap_number = 15
    vm._fuel_level = 2.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()
    # Disarm (refuel)
    vm._lap_number = 16
    vm._fuel_level = 60.0
    vm.recalculateLiveStrategy()
    plays.clear()

    # Re-arm later
    vm._lap_number = 35
    vm._fuel_level = 2.0
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is True
    assert len(plays) == 1


# ---------------------------------------------------------------------------
# Player swallows exceptions — a misbehaving cue must not crash recalc
# ---------------------------------------------------------------------------


def test_audio_player_exceptions_do_not_break_recalc() -> None:
    """Bootstrap may wire a real audio backend (QSoundEffect /
    OS player) that fails on missing devices, permissions, etc.
    A throwing player must not propagate up and break the per-
    lap recalc — the audio is *optional* in the strict sense."""
    vm = OverlayViewModel()

    def boom() -> None:
        raise RuntimeError("audio device unavailable")

    vm._pit_arm_audio_player = boom  # type: ignore[attr-defined]
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)

    vm._lap_number = 15
    vm._fuel_level = 2.0
    vm._fuel_per_lap = 3.0

    # Must not raise.
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is True
