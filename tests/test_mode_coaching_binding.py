"""T113: Mode change → coaching cadence change.

Per Q96, switching mode adjusts how verbose coaching is. T106's
``Mode.coaching_verbosity`` carries which level each mode wants
(``"off"`` / ``"minimal"`` / ``"verbose"``); T111's observer
hook fires on transitions; T113 ships the *binding* that ties
the two together.

The binding is a thin adapter: takes a ModeEngine + a target
that responds to ``set_verbosity(level)``, registers itself as
the engine's mode-changed observer, and forwards each new mode's
``coaching_verbosity`` to the target.

T119 (mid-session mode switch allowed but logged) means this
binding can fire mid-session. T103's "enabled flag is read at
session start" rule applies to the *user setting*, not to mode-
driven verbosity changes — those are first-class transitions.
"""
from __future__ import annotations

from lap_coach_logger.core.modes.engine import ModeEngine
from lap_coach_logger.core.modes.coaching_binding import (
    bind_coaching_verbosity_to_mode_engine,
)


class _FakeCoachingTarget:
    """Records ``set_verbosity`` calls so tests can assert
    against them without a real CoachingCardViewModel."""

    def __init__(self) -> None:
        self.verbosity_history: list[str] = []

    def set_verbosity(self, level: str) -> None:
        self.verbosity_history.append(level)


# ---------------------------------------------------------------------------
# Binding fires on mode change
# ---------------------------------------------------------------------------


def test_binding_forwards_new_modes_verbosity() -> None:
    engine = ModeEngine()  # default = practice ("verbose")
    target = _FakeCoachingTarget()
    bind_coaching_verbosity_to_mode_engine(engine, target=target)

    engine.set_mode("sprint")  # → "minimal"

    assert target.verbosity_history == ["minimal"]


def test_binding_passes_correct_verbosity_per_mode() -> None:
    """Sweep across the four modes — each carries its own
    verbosity. Catches a refactor that would, say, accidentally
    flip Sprint to "verbose" (race-distraction) or Practice to
    "minimal" (training under-coverage)."""
    engine = ModeEngine()
    target = _FakeCoachingTarget()
    bind_coaching_verbosity_to_mode_engine(engine, target=target)

    engine.set_mode("sprint")
    engine.set_mode("endurance")
    engine.set_mode("review")
    engine.set_mode("practice")

    assert target.verbosity_history == [
        "minimal",  # SprintMode
        "minimal",  # EnduranceMode
        "off",      # ReviewMode
        "verbose",  # PracticeMode
    ]


# ---------------------------------------------------------------------------
# Idempotent set_mode does not re-fire
# ---------------------------------------------------------------------------


def test_binding_does_not_fire_on_no_op_set_mode() -> None:
    engine = ModeEngine()
    target = _FakeCoachingTarget()
    engine.set_mode("sprint")  # before binding attaches
    bind_coaching_verbosity_to_mode_engine(engine, target=target)

    engine.set_mode("sprint")  # already sprint — no-op
    engine.set_mode("sprint")

    assert target.verbosity_history == []


# ---------------------------------------------------------------------------
# Initial sync option
# ---------------------------------------------------------------------------


def test_binding_can_optionally_sync_to_current_mode_on_attach() -> None:
    """At app startup, the coaching subsystem needs the engine's
    *current* mode verbosity from the first frame so the user's
    persisted mode (T117) actually takes effect."""
    engine = ModeEngine(default_mode_id="endurance")
    target = _FakeCoachingTarget()

    bind_coaching_verbosity_to_mode_engine(
        engine, target=target, sync_now=True
    )

    assert target.verbosity_history == ["minimal"]


def test_initial_sync_off_by_default() -> None:
    engine = ModeEngine()
    target = _FakeCoachingTarget()
    bind_coaching_verbosity_to_mode_engine(engine, target=target)

    assert target.verbosity_history == []


# ---------------------------------------------------------------------------
# CoachingCardViewModel integration
# ---------------------------------------------------------------------------


def test_coaching_vm_set_verbosity_off_disables_card() -> None:
    """The real CoachingCardViewModel reacts to set_verbosity by
    enabling/disabling its insight surface. ``"off"`` sets
    enabled to False — drains queue but surfaces nothing
    (T103 contract)."""
    from lap_coach_logger.coaching.rules_engine import (
        CoachingInsight,
        InsightQueue,
    )
    from lap_coach_logger.viewmodels.coaching_card_vm import (
        CoachingCardViewModel,
    )

    queue = InsightQueue()
    vm = CoachingCardViewModel(queue=queue, enabled=True)

    queue.publish([CoachingInsight(rule_id="x", payload={"title": "x"})])
    vm.set_verbosity("off")
    vm.poll()

    assert vm.has_insight is False


def test_coaching_vm_set_verbosity_verbose_enables_card() -> None:
    """``"verbose"`` (and ``"minimal"``) keep the card live —
    the cooldown-or-no-cooldown distinction within "live" is
    a future tuning concern (T092 cooldown is configurable)."""
    from lap_coach_logger.coaching.rules_engine import (
        CoachingInsight,
        InsightQueue,
    )
    from lap_coach_logger.viewmodels.coaching_card_vm import (
        CoachingCardViewModel,
    )

    queue = InsightQueue()
    vm = CoachingCardViewModel(queue=queue, enabled=False)

    vm.set_verbosity("verbose")
    queue.publish([CoachingInsight(rule_id="x", payload={"title": "x"})])
    vm.poll()

    assert vm.has_insight is True


def test_coaching_vm_set_verbosity_minimal_keeps_card_live() -> None:
    from lap_coach_logger.coaching.rules_engine import (
        CoachingInsight,
        InsightQueue,
    )
    from lap_coach_logger.viewmodels.coaching_card_vm import (
        CoachingCardViewModel,
    )

    queue = InsightQueue()
    vm = CoachingCardViewModel(queue=queue, enabled=False)

    vm.set_verbosity("minimal")
    queue.publish([CoachingInsight(rule_id="x", payload={"title": "x"})])
    vm.poll()

    assert vm.has_insight is True
