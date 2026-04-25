"""T143: manual arm / disarm override.

T140 / T141 ship the auto-arm pipeline. T143 adds the *user*
side: a button on the overlay (or a wheel-mapped action) that
lets the driver flip ``pitArmed`` directly. The driver's
intent must outweigh the auto-threshold — once they manually
arm or disarm, subsequent recalcs must not overwrite their
choice.

Slots on :class:`OverlayViewModel`:

- ``armPit()`` — set ``pitArmed = True``, latch override
- ``disarmPit()`` — set ``pitArmed = False``, latch override
- ``clearPitArmedOverride()`` — release control back to auto

Override semantics:

- Once latched, ``_refresh_pit_armed`` is a no-op so the user's
  choice persists through every per-lap recalc until they
  explicitly release.
- ``clearPitArmedOverride`` re-enables auto. The next recalc
  recomputes from telemetry as usual.
- Manual arm fires the audio cue (T142) on the False → True
  transition; manual disarm does not (cue is for "arm-up",
  not "stand down" — same rule as T142).
- Both slots are idempotent: arm() while already armed (or
  disarm() while already disarmed) is a no-op — no extra
  signal, no extra audio.
"""
from __future__ import annotations

from tests.qt_mock import install
install()

from lap_coach_logger.viewmodels.overlay_vm import OverlayViewModel  # noqa: E402


def _vm_with_strategy() -> OverlayViewModel:
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)
    return vm


# ---------------------------------------------------------------------------
# Direct slot effects
# ---------------------------------------------------------------------------


def test_arm_pit_sets_pit_armed_true() -> None:
    """User clicks the ARM button — pitArmed flips to True
    immediately. The simplest contract."""
    vm = _vm_with_strategy()

    vm.armPit()

    assert vm.pitArmed is True


def test_disarm_pit_sets_pit_armed_false() -> None:
    """Symmetric: user clicks DISARM — pitArmed flips to
    False."""
    vm = _vm_with_strategy()
    vm.armPit()
    assert vm.pitArmed is True

    vm.disarmPit()

    assert vm.pitArmed is False


# ---------------------------------------------------------------------------
# Override latches: auto-recalc respects the user's choice
# ---------------------------------------------------------------------------


def test_manual_arm_persists_through_healthy_recalc() -> None:
    """User arms manually because they have intel auto can't
    see (e.g., a planned strategy stop). Auto-recalc with
    healthy fuel/tire would normally disarm; the override must
    keep it armed."""
    vm = _vm_with_strategy()
    vm.armPit()

    vm._lap_number = 5
    vm._fuel_level = 50.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is True


def test_manual_disarm_persists_through_critical_recalc() -> None:
    """User disarms manually ("I'm staying out for one more
    lap"). Auto-recalc with critically low fuel would normally
    arm; the override must keep it disarmed."""
    vm = _vm_with_strategy()
    vm.disarmPit()  # explicit disarm latches override even from default-disarmed

    vm._lap_number = 15
    vm._fuel_level = 2.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is False


# ---------------------------------------------------------------------------
# Releasing control returns auto behaviour
# ---------------------------------------------------------------------------


def test_clear_override_re_enables_auto_arm() -> None:
    """User manually disarmed earlier; later they want auto
    back. After clearing the override the next recalc with
    critical telemetry must arm."""
    vm = _vm_with_strategy()
    vm.disarmPit()

    vm.clearPitArmedOverride()
    vm._lap_number = 15
    vm._fuel_level = 2.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is True


def test_clear_override_re_enables_auto_disarm() -> None:
    """Mirror: user manually armed for now-passed reasons.
    After clearing the override and a healthy recalc, auto
    disarms again."""
    vm = _vm_with_strategy()
    vm.armPit()

    vm.clearPitArmedOverride()
    vm._lap_number = 5
    vm._fuel_level = 50.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is False


# ---------------------------------------------------------------------------
# Audio cue mirrors T142 semantics: only on arm transitions
# ---------------------------------------------------------------------------


def test_manual_arm_fires_audio_cue() -> None:
    """Same audible signal whether user pressed ARM or auto
    fired — both are arm events from the driver's POV."""
    plays: list[None] = []
    vm = _vm_with_strategy()
    vm._pit_arm_audio_player = lambda: plays.append(None)

    vm.armPit()

    assert len(plays) == 1


def test_manual_disarm_does_not_fire_audio_cue() -> None:
    """Cue is for arm-up, not stand-down — same rule as T142.
    User dismissing pit doesn't need the alert sound."""
    plays: list[None] = []
    vm = _vm_with_strategy()
    vm.armPit()
    plays.clear()
    vm._pit_arm_audio_player = lambda: plays.append(None)

    vm.disarmPit()

    assert plays == []


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_arm_pit_when_already_armed_does_not_fire_signal() -> None:
    """Repeated ARM clicks (e.g., user mashing the button)
    must not double-fire the change signal — QML rebinds are
    expensive."""
    vm = _vm_with_strategy()
    vm.armPit()
    baseline = vm.pitArmedChanged.call_count

    vm.armPit()

    assert vm.pitArmedChanged.call_count == baseline


def test_arm_pit_when_already_armed_does_not_fire_audio() -> None:
    """Same idempotency for the audio cue — no nag."""
    plays: list[None] = []
    vm = _vm_with_strategy()
    vm._pit_arm_audio_player = lambda: plays.append(None)
    vm.armPit()
    assert len(plays) == 1

    vm.armPit()

    assert len(plays) == 1


def test_disarm_pit_when_already_disarmed_does_not_fire_signal() -> None:
    """Symmetric idempotency for disarm."""
    vm = _vm_with_strategy()
    baseline = vm.pitArmedChanged.call_count

    vm.disarmPit()  # already disarmed

    # disarmPit() may still latch the override even on no
    # state-change, but the change signal must not fire when
    # the *value* is unchanged.
    assert vm.pitArmedChanged.call_count == baseline


# ---------------------------------------------------------------------------
# Override is independent of telemetry: arming pre-baseline still works
# ---------------------------------------------------------------------------


def test_arm_pit_works_without_pre_race_strategy() -> None:
    """User can arm before they've configured a strategy
    (e.g., pre-race in a one-make spec series). The override
    must not require a baseline strategy — auto-recalc would
    no-op anyway with no plan."""
    vm = OverlayViewModel()  # no strategy set

    vm.armPit()

    assert vm.pitArmed is True
