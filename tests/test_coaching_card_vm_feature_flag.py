"""T103: Coaching view honours an enable/disable feature flag.

When the user has turned coaching OFF in settings, the
CoachingCardViewModel must:

- Not surface any insight (``has_insight`` stays False)
- Not fire audio cues
- Not queue insights for "later" (re-enabling doesn't replay
  history; that's surprising UX and would feel stale anyway)
- Still construct cleanly and respond to method calls (defensive
  no-op rather than raise — a refactor that wires the flag
  wrong shouldn't crash the live session)

Why a VM-level flag (not just "don't construct the VM"):
- The QML layout reserves space for the card whether or not
  it's enabled — toggling at session start would otherwise
  leave a gap or require a layout reflow.
- Mid-session enable/disable is out of scope (T093 same
  decision); the flag is read at session start, applies for
  the duration of the session.

Production wiring: bootstrap reads ``config.coaching_enabled``
(set via the settings UI) and passes ``enabled=`` to the VM.
"""
from __future__ import annotations

from lap_coach_logger.coaching.rules_engine import (
    CoachingInsight,
    InsightQueue,
)
from lap_coach_logger.viewmodels.coaching_card_vm import CoachingCardViewModel


def _insight(rule_id: str) -> CoachingInsight:
    return CoachingInsight(rule_id=rule_id, payload={"title": rule_id})


# ---------------------------------------------------------------------------
# Disabled VM: no insights surface
# ---------------------------------------------------------------------------


def test_disabled_vm_does_not_surface_insights_from_poll() -> None:
    """Even with insights pending in the queue, a disabled VM
    keeps ``has_insight`` False — coaching is off as far as the
    user is concerned."""
    queue = InsightQueue()
    queue.publish([_insight("br.late")])

    vm = CoachingCardViewModel(queue=queue, enabled=False)
    vm.poll()

    assert vm.has_insight is False
    assert vm.insight == {}


def test_disabled_vm_does_not_fire_audio_cue() -> None:
    """The cue is the audio counterpart of the visual card —
    if the card stays hidden, the cue stays silent. Otherwise
    the user would hear ghost dings on a "disabled" feature."""
    queue = InsightQueue()
    queue.publish([_insight("br.late")])
    cued: list[CoachingInsight] = []

    vm = CoachingCardViewModel(
        queue=queue, audio_player=cued.append, enabled=False
    )
    vm.poll()

    assert cued == []


def test_disabled_vm_drains_queue_so_re_enable_does_not_replay() -> None:
    """A user who toggles coaching off mid-session expects the
    feature to go away. If we *kept* insights in the queue,
    flipping back ON would replay stale advice for things that
    happened laps ago — surprising and confusing.

    Disabled poll still drains so the queue doesn't grow
    unboundedly (T101 throughput pin) AND a future re-enable
    (out-of-scope mid-session, but defensive) wouldn't replay."""
    queue = InsightQueue()
    queue.publish([_insight("br.late"), _insight("ac.apex_loss")])

    vm = CoachingCardViewModel(queue=queue, enabled=False)
    vm.poll()

    # Queue should be empty (drained), even though nothing surfaced
    assert queue.drain() == []


def test_disabled_vm_dismiss_is_a_safe_noop() -> None:
    """Defensive: if QML somehow fires dismiss on a disabled VM
    (e.g., a stale binding click during a fade-out), don't
    raise. The card was never shown, so dismiss has nothing to
    do."""
    queue = InsightQueue()
    queue.publish([_insight("br.late")])

    vm = CoachingCardViewModel(queue=queue, enabled=False)
    vm.poll()
    vm.dismiss()  # must not raise

    assert vm.has_insight is False


def test_disabled_vm_flag_as_wrong_is_a_safe_noop() -> None:
    """Same defensive reasoning: a stale flag click on a
    disabled VM must not raise and must not POST to backend."""
    queue = InsightQueue()
    queue.publish([_insight("br.late")])
    flagged: list[tuple[CoachingInsight, str]] = []

    vm = CoachingCardViewModel(
        queue=queue,
        flag_callback=lambda i, r: flagged.append((i, r)),
        enabled=False,
    )
    vm.poll()
    vm.flag_as_wrong("user_flagged")  # must not raise

    assert flagged == []


# ---------------------------------------------------------------------------
# Default and enabled paths still work as before
# ---------------------------------------------------------------------------


def test_enabled_default_is_true() -> None:
    """Backwards compat — T091/T092/T093/T096/T098 callers
    don't pass ``enabled=`` and must keep working."""
    queue = InsightQueue()
    queue.publish([_insight("br.late")])

    vm = CoachingCardViewModel(queue=queue)
    vm.poll()

    assert vm.has_insight is True


def test_explicitly_enabled_vm_shows_insights() -> None:
    queue = InsightQueue()
    queue.publish([_insight("br.late")])

    vm = CoachingCardViewModel(queue=queue, enabled=True)
    vm.poll()

    assert vm.insight["rule_id"] == "br.late"
