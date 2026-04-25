"""T111: ``ModeEngine`` — runtime mode selection + transitions.

Holds the registry of available modes (the four subclasses
T107-T110), tracks the current mode, and dispatches transitions.
T112-T114 wire its mode-change signal to overlay / coaching /
strategy subsystems; T117 persists the current mode across
restarts.

Default-on-construction is :class:`PracticeMode` per Q96 — most
desktop sessions start as practice, and the toolbar dropdown
(T116) lets the user switch.

Transition rules T111 doesn't enforce:
- T119 mid-session switch (the engine ALLOWS it; logging /
  tag-split is a downstream concern).
- T118 auto-detect from sim hint (lives separately so the
  engine can be exercised in tests without sim-detection
  plumbing).

The engine is meant to be cheap to construct and shareable —
all four mode instances are stateless (T106 contract).
"""
from __future__ import annotations

import pytest

from lap_coach_logger.core.modes import Mode
from lap_coach_logger.core.modes.endurance import EnduranceMode
from lap_coach_logger.core.modes.engine import ModeEngine, UnknownModeError
from lap_coach_logger.core.modes.practice import PracticeMode
from lap_coach_logger.core.modes.review import ReviewMode
from lap_coach_logger.core.modes.sprint import SprintMode


# ---------------------------------------------------------------------------
# Registry of available modes
# ---------------------------------------------------------------------------


def test_engine_registers_all_four_built_in_modes_by_default() -> None:
    """The engine ships pre-registered with the four T107-T110
    modes — no caller setup required for the standard
    deployment."""
    engine = ModeEngine()

    available_ids = {m.id for m in engine.available_modes}
    assert available_ids == {"practice", "sprint", "endurance", "review"}


def test_default_current_mode_is_practice() -> None:
    """Per Q96 — most desktop sessions start as practice. T117
    persistence overrides this when a saved mode loads, but the
    cold-start default is practice."""
    engine = ModeEngine()

    assert engine.current.id == "practice"
    assert isinstance(engine.current, PracticeMode)


def test_engine_can_be_constructed_with_explicit_default() -> None:
    """Tests / specialised deployments may want to start in a
    non-practice mode (e.g., a streamer config that wants
    Endurance default). Pin that the constructor accepts an
    override."""
    engine = ModeEngine(default_mode_id="sprint")

    assert engine.current.id == "sprint"
    assert isinstance(engine.current, SprintMode)


def test_explicit_default_must_be_a_known_mode() -> None:
    """A typo in the override is a programmer error worth
    surfacing immediately rather than silently falling back to
    practice."""
    with pytest.raises(UnknownModeError):
        ModeEngine(default_mode_id="grandprix")


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------


def test_set_mode_switches_to_named_mode() -> None:
    """Primary transition API — pass the mode id, get the
    instance back AND make it current."""
    engine = ModeEngine()

    new_mode = engine.set_mode("sprint")

    assert isinstance(new_mode, SprintMode)
    assert engine.current.id == "sprint"


def test_set_mode_unknown_id_raises_unknown_mode_error() -> None:
    """Typo'd mode id ⇒ typed error so callers can pattern-match
    instead of guessing at a generic ValueError."""
    engine = ModeEngine()

    with pytest.raises(UnknownModeError):
        engine.set_mode("does_not_exist")


def test_set_mode_to_same_mode_is_idempotent() -> None:
    """Switching to the already-current mode must not raise
    and must leave the current mode unchanged. UI dropdowns
    sometimes fire change events on the no-op selection
    (depending on which Qt signal the binding is on)."""
    engine = ModeEngine()
    engine.set_mode("sprint")

    engine.set_mode("sprint")  # same as current

    assert engine.current.id == "sprint"


def test_set_mode_returns_the_mode_instance() -> None:
    """Lets the caller chain or inspect: ``mode = engine.set_mode("review")
    if mode.coaching_verbosity == "off": ...``"""
    engine = ModeEngine()

    review = engine.set_mode("review")

    assert isinstance(review, ReviewMode)


# ---------------------------------------------------------------------------
# Mode-changed observer
# ---------------------------------------------------------------------------


def test_engine_notifies_observers_on_mode_change() -> None:
    """T112-T114 (overlay / coaching / strategy bindings) all
    react to mode change. The engine offers an observer hook so
    those subsystems wire cheaply (no need to poll ``current``
    every tick)."""
    engine = ModeEngine()
    observed: list[Mode] = []
    engine.on_mode_changed(observed.append)

    engine.set_mode("sprint")

    assert len(observed) == 1
    assert observed[0].id == "sprint"


def test_no_op_set_mode_does_not_notify_observers() -> None:
    """Re-setting to the current mode is idempotent (above) but
    must NOT notify observers — that would cause T112's overlay
    swap to re-run pointlessly."""
    engine = ModeEngine()
    observed: list[Mode] = []
    engine.on_mode_changed(observed.append)

    engine.set_mode("practice")  # already practice

    assert observed == []


def test_multiple_observers_each_called_on_mode_change() -> None:
    """T112 (overlay), T113 (coaching), T114 (strategy) each
    register independently. All three must fire on the same
    transition, in registration order."""
    engine = ModeEngine()
    fire_order: list[str] = []
    engine.on_mode_changed(lambda m: fire_order.append(f"a:{m.id}"))
    engine.on_mode_changed(lambda m: fire_order.append(f"b:{m.id}"))
    engine.on_mode_changed(lambda m: fire_order.append(f"c:{m.id}"))

    engine.set_mode("endurance")

    assert fire_order == ["a:endurance", "b:endurance", "c:endurance"]


# ---------------------------------------------------------------------------
# Mode lookup helper
# ---------------------------------------------------------------------------


def test_get_mode_by_id_returns_instance_without_switching() -> None:
    """Look up a mode WITHOUT making it current — useful for the
    toolbar dropdown (T116) that needs each mode's display
    name + binding info to render the menu."""
    engine = ModeEngine()
    engine.set_mode("sprint")

    practice = engine.get_mode("practice")

    assert isinstance(practice, PracticeMode)
    assert engine.current.id == "sprint"  # didn't change


def test_get_mode_by_id_unknown_raises_unknown_mode_error() -> None:
    engine = ModeEngine()

    with pytest.raises(UnknownModeError):
        engine.get_mode("nope")


# ---------------------------------------------------------------------------
# Endurance / Review reachability
# ---------------------------------------------------------------------------


def test_engine_supports_all_four_modes_round_trip() -> None:
    """Smoke test: can switch to each of the four built-ins,
    each is the right concrete class. Catches a registry typo
    that would silently swap two modes."""
    engine = ModeEngine()

    assert isinstance(engine.set_mode("practice"), PracticeMode)
    assert isinstance(engine.set_mode("sprint"), SprintMode)
    assert isinstance(engine.set_mode("endurance"), EnduranceMode)
    assert isinstance(engine.set_mode("review"), ReviewMode)
