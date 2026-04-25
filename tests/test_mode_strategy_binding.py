"""T114: Mode change → strategy safety-margin change.

Per Q96, switching mode adjusts strategy assumptions — fuel
margin, time padding, risk tolerance. T106's
``Mode.strategy_safety_margin`` carries the scalar each mode
wants (0.0 for Practice/Review, 0.05 for Sprint, 0.12 for
Endurance per T107-T110); T111's observer hook fires on
transitions; T114 ships the *binding* that ties the two together.

Mirrors T112 (overlay) and T113 (coaching) shape: thin adapter
takes a ModeEngine + a target that responds to
``set_safety_margin(margin)``, registers as the engine's
mode-changed observer, and forwards each new mode's
``strategy_safety_margin`` to the target.

What T114 does NOT do:
- Replace a real strategy engine — that's a separate sprint
  block (Block H — T136-T155 strategy + pit-armed). T114 just
  plumbs the engine into whatever interface the strategy
  system exposes.
- Apply the margin (fuel calc, etc.) — strategy logic owns
  that. T114 only carries the value across.

The fake-target test pattern matches T112/T113 — production
wiring composes the real strategy engine; tests inject a
list-recording stub.
"""
from __future__ import annotations

from lap_coach_logger.core.modes.engine import ModeEngine
from lap_coach_logger.core.modes.strategy_binding import (
    bind_strategy_safety_margin_to_mode_engine,
)


class _FakeStrategyTarget:
    """Records ``set_safety_margin`` calls so tests can assert
    against them without a real strategy engine in scope."""

    def __init__(self) -> None:
        self.margin_history: list[float] = []

    def set_safety_margin(self, margin: float) -> None:
        self.margin_history.append(margin)


# ---------------------------------------------------------------------------
# Binding fires on mode change
# ---------------------------------------------------------------------------


def test_binding_forwards_new_modes_safety_margin() -> None:
    engine = ModeEngine()  # default = practice (0.0)
    target = _FakeStrategyTarget()
    bind_strategy_safety_margin_to_mode_engine(engine, target=target)

    engine.set_mode("sprint")  # → 0.05

    assert target.margin_history == [0.05]


def test_binding_passes_correct_margin_per_mode() -> None:
    """Sweep across the four modes — each carries its own
    margin per T107-T110. Cross-checks both the per-mode
    constants AND T114's wiring. Catches a refactor that
    would, say, accidentally swap Sprint and Endurance
    margins (would lose endurance pace OR DNF sprint races)."""
    engine = ModeEngine()
    target = _FakeStrategyTarget()
    bind_strategy_safety_margin_to_mode_engine(engine, target=target)

    engine.set_mode("sprint")
    engine.set_mode("endurance")
    engine.set_mode("review")
    engine.set_mode("practice")

    assert target.margin_history == [
        0.05,  # SprintMode
        0.12,  # EnduranceMode
        0.0,   # ReviewMode
        0.0,   # PracticeMode
    ]


# ---------------------------------------------------------------------------
# Idempotent set_mode does not re-fire
# ---------------------------------------------------------------------------


def test_binding_does_not_fire_on_no_op_set_mode() -> None:
    """T111 doesn't notify observers when set_mode is a no-op
    (already-current mode). T114 inherits that — re-selecting
    the same mode in the toolbar must NOT re-publish the same
    safety margin."""
    engine = ModeEngine()
    engine.set_mode("sprint")  # before binding attaches
    target = _FakeStrategyTarget()
    bind_strategy_safety_margin_to_mode_engine(engine, target=target)

    engine.set_mode("sprint")  # already sprint — no-op
    engine.set_mode("sprint")

    assert target.margin_history == []


# ---------------------------------------------------------------------------
# Initial sync option
# ---------------------------------------------------------------------------


def test_binding_can_optionally_sync_to_current_mode_on_attach() -> None:
    """At app startup, the strategy subsystem needs the engine's
    *current* mode margin from the first frame so the persisted
    mode (T117) actually controls fuel/time projections from
    lap one."""
    engine = ModeEngine(default_mode_id="endurance")
    target = _FakeStrategyTarget()

    bind_strategy_safety_margin_to_mode_engine(
        engine, target=target, sync_now=True
    )

    assert target.margin_history == [0.12]


def test_initial_sync_off_by_default() -> None:
    engine = ModeEngine()
    target = _FakeStrategyTarget()
    bind_strategy_safety_margin_to_mode_engine(engine, target=target)

    assert target.margin_history == []


# ---------------------------------------------------------------------------
# Cross-mode invariant: endurance > sprint
# ---------------------------------------------------------------------------


def test_endurance_margin_strictly_greater_than_sprint_via_binding() -> None:
    """End-to-end pin of the T109 cross-mode invariant
    (endurance margin > sprint margin) through the binding
    layer. Catches a refactor that would accidentally swap
    the constants AND a binding bug that would mis-forward
    the values."""
    engine = ModeEngine()
    target = _FakeStrategyTarget()
    bind_strategy_safety_margin_to_mode_engine(engine, target=target)

    engine.set_mode("sprint")
    sprint_margin = target.margin_history[-1]
    engine.set_mode("endurance")
    endurance_margin = target.margin_history[-1]

    assert endurance_margin > sprint_margin
