"""T112: Mode change → overlay preset switch.

Per Q96, switching mode swaps the overlay widget set within a
frame. T106's Mode.overlay_preset_id carries which preset each
mode uses; T111's observer hook fires on transitions; T112 ships
the *binding* that ties the two together.

The binding is a thin adapter: takes a ModeEngine + a target
that responds to ``set_preset(preset_id)``, registers itself as
the engine's mode-changed observer, and forwards each new mode's
``overlay_preset_id`` to the target.

What T112 deliberately does NOT do:
- Replace the existing OverlayManager / preset system (lives in
  src/lap_coach_logger/qml/...). T121-T125 ship the preset
  refactor; T112 just plumbs the engine into whatever interface
  the preset system exposes.
- Persist the chosen preset (T134's job).

The fake-target test pattern is what T091's audio_player /
T098's flag_callback already use — production wiring composes
the real preset switcher; tests inject a list-recording stub.
"""
from __future__ import annotations

from lap_coach_logger.core.modes import Mode
from lap_coach_logger.core.modes.engine import ModeEngine
from lap_coach_logger.core.modes.overlay_binding import (
    bind_overlay_preset_to_mode_engine,
)


class _FakeOverlayTarget:
    """Records ``set_preset`` calls so tests can assert against
    them without a real QML overlay system in scope."""

    def __init__(self) -> None:
        self.preset_history: list[str] = []

    def set_preset(self, preset_id: str) -> None:
        self.preset_history.append(preset_id)


# ---------------------------------------------------------------------------
# Binding fires preset changes on mode change
# ---------------------------------------------------------------------------


def test_binding_forwards_new_modes_preset_to_target() -> None:
    engine = ModeEngine()  # default = practice
    target = _FakeOverlayTarget()

    bind_overlay_preset_to_mode_engine(engine, target=target)

    engine.set_mode("sprint")  # → preset "race-minimal"

    assert target.preset_history == ["race-minimal"]


def test_binding_uses_target_set_preset_method() -> None:
    """Pin the method shape — a refactor renaming
    ``set_preset`` (e.g., to ``apply_preset``) would silently
    pass this test if it didn't actually call anything,
    because the fake target only records what's called."""
    engine = ModeEngine()
    target = _FakeOverlayTarget()
    bind_overlay_preset_to_mode_engine(engine, target=target)

    engine.set_mode("review")

    # If method shape changed, history would be empty
    assert len(target.preset_history) == 1


def test_binding_passes_correct_preset_per_mode() -> None:
    """Sweep across the four modes, verify each one's
    ``overlay_preset_id`` reaches the target. Cross-checks
    T106-T110's per-mode constants AND T112's wiring."""
    engine = ModeEngine()
    target = _FakeOverlayTarget()
    bind_overlay_preset_to_mode_engine(engine, target=target)

    # Default is practice; switch through the other three
    engine.set_mode("sprint")
    engine.set_mode("endurance")
    engine.set_mode("review")

    assert target.preset_history == [
        "race-minimal",  # SprintMode
        "endurance",     # EnduranceMode
        "race-minimal",  # ReviewMode (quietest live preset)
    ]


# ---------------------------------------------------------------------------
# Idempotent set_mode does not re-fire preset switch
# ---------------------------------------------------------------------------


def test_binding_does_not_fire_on_no_op_set_mode() -> None:
    """T111 doesn't notify observers when set_mode is a no-op
    (already-current mode). T112 inherits that — re-selecting
    the same mode in the toolbar must NOT reload the overlay
    preset (would cause a visible flicker on every dropdown
    click that doesn't change anything)."""
    engine = ModeEngine()
    engine.set_mode("sprint")
    target = _FakeOverlayTarget()
    bind_overlay_preset_to_mode_engine(engine, target=target)

    engine.set_mode("sprint")  # already sprint — no-op
    engine.set_mode("sprint")  # still no-op

    assert target.preset_history == []


# ---------------------------------------------------------------------------
# Initial sync option
# ---------------------------------------------------------------------------


def test_binding_can_optionally_sync_target_to_current_mode_on_attach() -> None:
    """At app startup, the overlay system is uninitialised but
    the engine is already in default-practice. Without an
    initial sync, the overlay would render in some default
    preset until the user clicks the dropdown to "change".
    Initial sync brings the target up-to-date the moment the
    binding attaches."""
    engine = ModeEngine(default_mode_id="endurance")
    target = _FakeOverlayTarget()

    bind_overlay_preset_to_mode_engine(
        engine, target=target, sync_now=True
    )

    assert target.preset_history == ["endurance"]


def test_initial_sync_is_off_by_default() -> None:
    """Backward compat — existing test cases (above) shouldn't
    suddenly see an extra preset write at attach time."""
    engine = ModeEngine()
    target = _FakeOverlayTarget()
    bind_overlay_preset_to_mode_engine(engine, target=target)

    assert target.preset_history == []
