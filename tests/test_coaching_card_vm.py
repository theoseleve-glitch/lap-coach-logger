"""T091: ``CoachingCardViewModel`` consumes the insight stream
from the rules engine and exposes it to QML.

T082's :class:`InsightQueue` carries insights from the sample
thread to the VM thread. T091 wires the VM that drains the queue
and republishes via Qt's binding model so QML can render the
current insight.

Minimal contract:

- ``insight`` (Property, str/dict): the currently-shown insight
  payload as a ``QVariant``. Empty dict when nothing is shown.
- ``poll()`` (Slot): drains the queue. Called periodically by
  Qt (timer, T091 doesn't own scheduling).
- ``dismiss()`` (Slot): clears the current insight. Pending
  insights advance.
- ``insightChanged`` (Signal): fires when the current insight
  swaps (new one shown, current cleared).

What T091 does NOT do (and what owns those concerns):
- Cooldown / dedupe between same rule firing repeatedly → T092.
- Skill-level variant selection (beginner / intermediate /
  advanced) → T093.
- Audio cue → T096.
- Dismiss animation / fade out → T094 / T095.
"""
from __future__ import annotations

from lap_coach_logger.coaching.rules_engine import (
    CoachingInsight,
    InsightCooldownFilter,
    InsightQueue,
)
from lap_coach_logger.viewmodels.coaching_card_vm import CoachingCardViewModel


def _insight(rule_id: str, **extras) -> CoachingInsight:
    payload = {"title": rule_id, **extras}
    return CoachingInsight(rule_id=rule_id, payload=payload)


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_state_shows_nothing() -> None:
    """Pre-poll, before any insights have arrived, the VM must
    expose an empty payload — QML's ``vm.insight.title || ""``
    pattern needs the insight to be a dict (not None) so the
    property access works."""
    queue = InsightQueue()
    vm = CoachingCardViewModel(queue=queue)

    assert vm.insight == {}
    assert vm.has_insight is False


# ---------------------------------------------------------------------------
# Polling pulls from queue
# ---------------------------------------------------------------------------


def test_poll_consumes_first_insight_and_updates_property() -> None:
    """The VM polls the queue (Qt timer drives this externally).
    First insight in the queue becomes the current insight; the
    property reflects its payload + rule_id."""
    queue = InsightQueue()
    queue.publish([_insight("br.late_braking", rationale="brake later")])

    vm = CoachingCardViewModel(queue=queue)
    vm.poll()

    assert vm.has_insight is True
    assert vm.insight["rule_id"] == "br.late_braking"
    assert vm.insight["title"] == "br.late_braking"
    assert vm.insight["rationale"] == "brake later"


def test_poll_emits_insight_changed_signal_when_new_insight_arrives() -> None:
    """QML bindings need to update — that requires
    ``insightChanged`` to fire. Without this signal the property
    value would change but QML would never re-render."""
    queue = InsightQueue()
    vm = CoachingCardViewModel(queue=queue)
    fire_count = [0]
    vm.insightChanged.connect(lambda: fire_count.__setitem__(0, fire_count[0] + 1))

    queue.publish([_insight("br.late")])
    vm.poll()

    assert fire_count[0] == 1


def test_poll_with_empty_queue_does_not_emit_signal() -> None:
    """Polling when nothing's pending must NOT fire the signal —
    that would cause QML to needlessly re-evaluate every binding
    on every poll tick (Qt timer = many per second)."""
    queue = InsightQueue()
    vm = CoachingCardViewModel(queue=queue)
    fire_count = [0]
    vm.insightChanged.connect(lambda: fire_count.__setitem__(0, fire_count[0] + 1))

    vm.poll()  # empty queue
    vm.poll()
    vm.poll()

    assert fire_count[0] == 0


def test_poll_advances_to_next_pending_after_current_set() -> None:
    """If multiple insights arrive before the user dismisses,
    the VM holds on to them — first one is shown immediately,
    the others queue up internally (T097 dismiss → next).

    Pinning here prevents an "always show latest" bug where
    rapidly-fired insights flicker through the card."""
    queue = InsightQueue()
    queue.publish(
        [_insight("first"), _insight("second"), _insight("third")]
    )
    vm = CoachingCardViewModel(queue=queue)

    vm.poll()

    # Showing FIRST, not THIRD — order is preserved
    assert vm.insight["rule_id"] == "first"


# ---------------------------------------------------------------------------
# Dismiss advances to next pending
# ---------------------------------------------------------------------------


def test_dismiss_clears_current_when_no_pending() -> None:
    queue = InsightQueue()
    queue.publish([_insight("only_one")])
    vm = CoachingCardViewModel(queue=queue)
    vm.poll()

    vm.dismiss()

    assert vm.has_insight is False
    assert vm.insight == {}


def test_dismiss_advances_to_next_pending_insight() -> None:
    """T097 will wire a dismiss button. The VM contract: dismiss
    pops the next queued insight if there is one, so the user
    sees the next coaching card without an extra poll."""
    queue = InsightQueue()
    queue.publish([_insight("first"), _insight("second")])
    vm = CoachingCardViewModel(queue=queue)
    vm.poll()  # current = first; pending = [second]

    vm.dismiss()  # current = second

    assert vm.insight["rule_id"] == "second"


def test_dismiss_emits_insight_changed_signal() -> None:
    """A swap from "shown" to "nothing shown" is a binding update
    — QML's ``visible`` binding on the card needs to react."""
    queue = InsightQueue()
    queue.publish([_insight("first")])
    vm = CoachingCardViewModel(queue=queue)
    vm.poll()
    fire_count = [0]
    vm.insightChanged.connect(lambda: fire_count.__setitem__(0, fire_count[0] + 1))

    vm.dismiss()

    assert fire_count[0] == 1


def test_dismiss_when_no_current_is_a_noop() -> None:
    """Defensive: a user clicks dismiss on an empty state (for
    example a stale binding click). Must not raise."""
    queue = InsightQueue()
    vm = CoachingCardViewModel(queue=queue)

    vm.dismiss()  # no current, no pending
    vm.dismiss()  # second time
    assert vm.has_insight is False


# ---------------------------------------------------------------------------
# Multiple poll cycles accumulate pending insights
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T092: Cooldown filter integration
# ---------------------------------------------------------------------------


def test_vm_with_cooldown_drops_repeated_same_rule_insight() -> None:
    """The VM honours its cooldown filter: a second fire of the
    same rule within the cooldown window does NOT show a card.

    Pinning here ensures T092's cooldown actually flows through
    the VM — the InsightCooldownFilter unit tests cover the
    filter's own semantics; this one covers wiring."""
    queue = InsightQueue()
    clock = [1000.0]
    cooldown = InsightCooldownFilter(
        cooldown_seconds=30.0, now=lambda: clock[0]
    )
    vm = CoachingCardViewModel(queue=queue, cooldown_filter=cooldown)

    queue.publish([_insight("br.late")])
    vm.poll()  # shows br.late
    vm.dismiss()  # user moves on

    queue.publish([_insight("br.late")])
    clock[0] = 1010.0  # 10s later — within cooldown
    vm.poll()

    assert vm.has_insight is False  # filtered out


def test_vm_with_cooldown_passes_repeat_after_window_expires() -> None:
    queue = InsightQueue()
    clock = [1000.0]
    cooldown = InsightCooldownFilter(
        cooldown_seconds=30.0, now=lambda: clock[0]
    )
    vm = CoachingCardViewModel(queue=queue, cooldown_filter=cooldown)

    queue.publish([_insight("br.late")])
    vm.poll()
    vm.dismiss()

    queue.publish([_insight("br.late")])
    clock[0] = 1030.5  # past cooldown
    vm.poll()

    assert vm.insight["rule_id"] == "br.late"


def test_subsequent_polls_append_to_pending() -> None:
    """User is reading a card; meanwhile two more insights fire
    over the next two laps. Polls between laps drain the queue
    and queue them after the current one. The user sees them
    when they dismiss."""
    queue = InsightQueue()
    queue.publish([_insight("first")])
    vm = CoachingCardViewModel(queue=queue)
    vm.poll()  # current = first

    queue.publish([_insight("second")])
    vm.poll()  # current still first; pending = [second]
    queue.publish([_insight("third")])
    vm.poll()  # pending = [second, third]

    vm.dismiss()
    assert vm.insight["rule_id"] == "second"
    vm.dismiss()
    assert vm.insight["rule_id"] == "third"
    vm.dismiss()
    assert vm.has_insight is False
