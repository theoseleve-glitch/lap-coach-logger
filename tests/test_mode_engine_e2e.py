"""T120: End-to-end mode-switch composition.

Block G's individual binding tests (T112 overlay, T113 coaching,
T114 strategy) each pin their own slice of the
``ModeEngine.on_mode_changed`` contract. T120 is the *composition*
sweep: spin up a real engine, attach all three bindings to a
fake target, then assert that a single ``engine.set_mode("sprint")``
call from the default Practice mode advances every consumer in
lockstep — same way production wires them at app startup.

The headline assertion lives in the spec:

    "switch Practice→Sprint, verify overlay changes"

This module covers that and adds the cross-binding cross-checks
(coaching + strategy) so a refactor that breaks the observer
contract for one consumer can't sneak through by passing the
overlay-only test.

No new production code — T120 exercises the existing T106-T114
stack as a unit. Failures here mean either the engine stopped
notifying observers or one of the bindings stopped honouring
the contract.
"""
from __future__ import annotations

from lap_coach_logger.core.modes.coaching_binding import (
    bind_coaching_verbosity_to_mode_engine,
)
from lap_coach_logger.core.modes.engine import ModeEngine
from lap_coach_logger.core.modes.overlay_binding import (
    bind_overlay_preset_to_mode_engine,
)
from lap_coach_logger.core.modes.strategy_binding import (
    bind_strategy_safety_margin_to_mode_engine,
)


class _FakeWorld:
    """Records every set_* call the bindings drive, in the order
    they fire. Combines the three target Protocols (set_preset /
    set_verbosity / set_safety_margin) so one fixture spans all
    three bindings — matches how production composes them
    against a single overlay-coaching-strategy stack."""

    def __init__(self) -> None:
        self.preset_history: list[str] = []
        self.verbosity_history: list[str] = []
        self.margin_history: list[float] = []

    # T112 target shape
    def set_preset(self, preset_id: str) -> None:
        self.preset_history.append(preset_id)

    # T113 target shape
    def set_verbosity(self, level: str) -> None:
        self.verbosity_history.append(level)

    # T114 target shape
    def set_safety_margin(self, margin: float) -> None:
        self.margin_history.append(margin)


def _wire(engine: ModeEngine, world: _FakeWorld, *, sync_now: bool = False) -> None:
    bind_overlay_preset_to_mode_engine(engine, target=world, sync_now=sync_now)
    bind_coaching_verbosity_to_mode_engine(engine, target=world, sync_now=sync_now)
    bind_strategy_safety_margin_to_mode_engine(engine, target=world, sync_now=sync_now)


# ---------------------------------------------------------------------------
# Headline E2E: Practice → Sprint advances every consumer
# ---------------------------------------------------------------------------


def test_switching_practice_to_sprint_changes_overlay_preset() -> None:
    """The exact T120 spec line: Practice→Sprint, overlay changes.
    Pinned as its own test (no other assertions) so the failure
    message points straight at the headline contract if it
    breaks."""
    engine = ModeEngine()  # default = practice
    world = _FakeWorld()
    _wire(engine, world)

    engine.set_mode("sprint")

    assert world.preset_history == ["race-minimal"]


def test_switching_practice_to_sprint_advances_all_three_bindings() -> None:
    """Composition cross-check: one set_mode call must advance
    overlay AND coaching AND strategy. Catches a regression
    where the engine somehow notifies one observer but not
    the others (e.g., an early-return after the first
    callback)."""
    engine = ModeEngine()
    world = _FakeWorld()
    _wire(engine, world)

    engine.set_mode("sprint")

    assert world.preset_history == ["race-minimal"]      # T112
    assert world.verbosity_history == ["minimal"]        # T113
    assert world.margin_history == [0.05]                # T114


# ---------------------------------------------------------------------------
# Round-trip: Practice → Sprint → Practice
# ---------------------------------------------------------------------------


def test_round_trip_practice_sprint_practice_replays_each_consumer() -> None:
    """Pin both directions of the transition. A subtle observer-
    list bug (e.g., observers that fire only on the first
    transition) wouldn't be caught by a one-shot test."""
    engine = ModeEngine()
    world = _FakeWorld()
    _wire(engine, world)

    engine.set_mode("sprint")
    engine.set_mode("practice")

    assert world.preset_history == ["race-minimal", "practice"]
    assert world.verbosity_history == ["minimal", "verbose"]
    assert world.margin_history == [0.05, 0.0]


# ---------------------------------------------------------------------------
# Idempotent set_mode does NOT replay across the binding stack
# ---------------------------------------------------------------------------


def test_re_selecting_active_mode_does_not_replay_observers() -> None:
    """``ModeEngine.set_mode`` is idempotent (T111) — repeated
    calls to the active mode are no-ops and must NOT fire
    observers. Pinning this end-to-end so a regression that
    re-fires on no-op set_mode (e.g., dropping the early-
    return) gets caught at the composition layer."""
    engine = ModeEngine()
    world = _FakeWorld()
    _wire(engine, world)

    engine.set_mode("sprint")
    engine.set_mode("sprint")  # no-op
    engine.set_mode("sprint")  # no-op

    assert world.preset_history == ["race-minimal"]
    assert world.verbosity_history == ["minimal"]
    assert world.margin_history == [0.05]


# ---------------------------------------------------------------------------
# sync_now bootstrap: app start delivers default mode without a switch
# ---------------------------------------------------------------------------


def test_sync_now_bootstrap_delivers_default_mode_to_every_consumer() -> None:
    """At app startup, T117's persisted-mode loader picks the
    starting mode; the bindings are then wired with
    ``sync_now=True`` so each consumer receives the bootstrap
    state without waiting for a user-initiated switch. End-to-
    end pin: the default (Practice) reaches all three consumers
    on attach."""
    engine = ModeEngine()  # default = practice
    world = _FakeWorld()
    _wire(engine, world, sync_now=True)

    # No set_mode calls. All three bindings should have fired
    # against the engine's current mode (Practice).
    assert world.preset_history == ["practice"]
    assert world.verbosity_history == ["verbose"]
    assert world.margin_history == [0.0]
