"""T135: Block G end-to-end smoke — install → default preset →
switch to Practice mode → preset changes.

T120 already pins the overlay/coaching/strategy binding stack
across mode transitions. T135's distinct contribution is the
*install* end of the flow:

- T126's :func:`default_preset_id_on_first_install` is the
  bootstrap source of truth when no persistence (T117) and no
  sim-hint (T118) speak up.
- The first preset the overlay receives must equal that default.
- A user-initiated switch to Practice mode then advances the
  overlay to the Practice preset id.
- That id resolves through :func:`get_builtin_preset` to the
  canonical T123 :data:`PRACTICE_PRESET`, with all 12 widgets
  including the technique-focused additions (inputs / g_g /
  live_trace / pedal_trace) that distinguish Practice from
  race-minimal.

Any regression along T106 (Mode classes) → T111 (engine) →
T112 (overlay binding) → T122/T123 (preset definitions) →
T126 (first-install default) breaks this single test.

No new production code — pure composition.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lap_coach_logger.core.modes.builtin_presets import (
    default_preset_id_on_first_install,
    get_builtin_preset,
)
from lap_coach_logger.core.modes.engine import ModeEngine
from lap_coach_logger.core.modes.overlay_binding import (
    bind_overlay_preset_to_mode_engine,
)


@dataclass
class _RecordingOverlayTarget:
    """Records every preset id the binding pushes — the
    sequence (not just the final value) is what the E2E pins,
    so a regression that fires duplicate or out-of-order events
    can't sneak through a final-state-only assertion."""

    preset_ids: list[str] = field(default_factory=list)

    def set_preset(self, preset_id: str) -> None:
        self.preset_ids.append(preset_id)


# ---------------------------------------------------------------------------
# Headline E2E: install → default preset → Practice → preset changes
# ---------------------------------------------------------------------------


def test_install_to_practice_changes_overlay_preset_to_practice() -> None:
    """Spec line verbatim: install → default preset → switch to
    Practice mode → preset changes ⇒ green.

    SprintMode is the mode whose ``overlay_preset_id`` matches
    T126's first-install default (race-minimal); attaching the
    binding with ``sync_now=True`` mimics how production wires
    the overlay at app startup before any user input."""
    target = _RecordingOverlayTarget()
    engine = ModeEngine(default_mode_id="sprint")
    bind_overlay_preset_to_mode_engine(engine, target=target, sync_now=True)

    # Step 1: install state surfaces the canonical default.
    assert target.preset_ids[-1] == default_preset_id_on_first_install()
    assert target.preset_ids[-1] == "race-minimal"

    # Step 2: user switches to Practice mode.
    engine.set_mode("practice")

    # Step 3: overlay receives the Practice preset id.
    assert target.preset_ids[-1] == "practice"


def test_practice_preset_id_resolves_to_canonical_12_widget_preset() -> None:
    """The preset_id the binding pushes is only useful if the
    overlay can resolve it to a real :class:`ModeOverlayPreset`.
    Pin the resolution path against the canonical T123 preset so
    a future rename of the preset id (or a missing entry in
    ``_BUILTIN_PRESETS``) gets caught at the E2E layer too."""
    target = _RecordingOverlayTarget()
    engine = ModeEngine(default_mode_id="sprint")
    bind_overlay_preset_to_mode_engine(engine, target=target, sync_now=True)

    engine.set_mode("practice")

    practice_preset = get_builtin_preset(target.preset_ids[-1])
    assert practice_preset is not None
    assert practice_preset.preset_id == "practice"
    assert len(practice_preset.widgets) == 12

    widget_ids = {w.widget_id for w in practice_preset.widgets}
    # Practice-only technique additions (race-minimal core is
    # cross-checked by T123's own tests; here we only pin the
    # *delta* so future tweaks to the race-minimal core don't
    # cascade into a Block G E2E failure).
    assert {"inputs", "g_g", "live_trace", "pedal_trace"} <= widget_ids


# ---------------------------------------------------------------------------
# Sequence pin: bootstrap then user-switch produces a clean two-step history
# ---------------------------------------------------------------------------


def test_install_then_switch_history_is_default_then_practice() -> None:
    """Pin the *full* preset_id sequence — catches a regression
    where the binding fires duplicate sync events (e.g.,
    ``sync_now=True`` plus a self-triggered initial set_mode) or
    swallows the user-initiated switch."""
    target = _RecordingOverlayTarget()
    engine = ModeEngine(default_mode_id="sprint")
    bind_overlay_preset_to_mode_engine(engine, target=target, sync_now=True)

    engine.set_mode("practice")

    assert target.preset_ids == [
        default_preset_id_on_first_install(),
        "practice",
    ]
