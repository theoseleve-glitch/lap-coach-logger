"""T096: Audio cue option for coaching cards.

When a coaching card swaps in (new insight becomes current),
optionally fire an audio cue. The cue is "configurable" — the
caller injects an audio player callback at construction time;
``None`` opts out entirely.

Why a callback, not a built-in audio engine:
- The audio engine (TTS or sound file) is platform-specific
  and out of scope for the VM. T096 ships the wiring; T103 / a
  later UI task plugs the actual player (likely Qt MediaPlayer
  in QML, or a pyttsx3 TTS bridge).
- The callback shape (``CoachingInsight → None``) lets the player
  decide whether to read the title verbatim, play a generic
  ding, or pick a category-specific sound effect — without
  forcing T096 to know about any of that.

Configurability surfaces via:
- The constructor's ``audio_player`` param. ``None`` = silent.
- The injection point lets the user setting ("Enable voice cues")
  drive the behaviour: settings UI on/off → constructor receives
  a real player or ``None``. No mid-session toggling — T093's
  decision applies here too (read at session start; mid-session
  changes out of scope).

Audio fires when the **current** insight changes (poll integrates
a new one, or dismiss pops the next). Pending insights queued
behind the current one don't fire — they'll fire when they
become current via dismiss.
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
# Audio player called on new current insight
# ---------------------------------------------------------------------------


def test_audio_player_fires_when_first_insight_arrives() -> None:
    """An empty card transitions to "showing X" — that's the
    moment the cue plays. The user's eye may be on the track,
    so the cue is the audio counterpart to the visual card."""
    queue = InsightQueue()
    queue.publish([_insight("br.late")])
    played: list[CoachingInsight] = []

    vm = CoachingCardViewModel(queue=queue, audio_player=played.append)
    vm.poll()

    assert len(played) == 1
    assert played[0].rule_id == "br.late"


def test_audio_player_fires_again_when_dismiss_advances_to_next() -> None:
    """User dismisses the brake-late card; the apex-loss card
    becomes current. Audio cue plays again — the user's eye may
    have returned to the apex-loss card already; the cue confirms
    "yes, this is a new tip"."""
    queue = InsightQueue()
    queue.publish([_insight("br.late"), _insight("ac.apex_loss")])
    played: list[CoachingInsight] = []

    vm = CoachingCardViewModel(queue=queue, audio_player=played.append)
    vm.poll()  # plays for br.late
    vm.dismiss()  # advances to ac.apex_loss; should play

    assert [i.rule_id for i in played] == ["br.late", "ac.apex_loss"]


def test_audio_player_does_not_fire_for_pending_insights() -> None:
    """First insight becomes current; the rest queue behind it.
    Cue plays for the *current* one only — the queued ones will
    cue when they become current via dismiss."""
    queue = InsightQueue()
    queue.publish(
        [_insight("first"), _insight("second"), _insight("third")]
    )
    played: list[CoachingInsight] = []

    vm = CoachingCardViewModel(queue=queue, audio_player=played.append)
    vm.poll()

    assert [i.rule_id for i in played] == ["first"]


# ---------------------------------------------------------------------------
# Audio player NOT called when no current insight
# ---------------------------------------------------------------------------


def test_audio_player_does_not_fire_on_empty_poll() -> None:
    """Poll with empty queue — nothing changes, no cue. Otherwise
    the cue would play on every Qt timer tick, making the user
    want to throw the headphones across the room."""
    queue = InsightQueue()
    played: list[CoachingInsight] = []

    vm = CoachingCardViewModel(queue=queue, audio_player=played.append)
    vm.poll()
    vm.poll()
    vm.poll()

    assert played == []


def test_audio_player_does_not_fire_when_dismiss_clears_to_empty() -> None:
    """Dismissing the last insight transitions to "nothing shown"
    — that's a cue-suppress, not a cue-play. The player only
    fires for new *content*, not for absence."""
    queue = InsightQueue()
    queue.publish([_insight("only_one")])
    played: list[CoachingInsight] = []

    vm = CoachingCardViewModel(queue=queue, audio_player=played.append)
    vm.poll()  # plays
    played.clear()

    vm.dismiss()  # clears to empty; no cue

    assert played == []


# ---------------------------------------------------------------------------
# Configurability — None opts out entirely
# ---------------------------------------------------------------------------


def test_audio_player_none_means_silent() -> None:
    """``audio_player=None`` is the explicit "off" config. Must
    not crash, must not fire — the user has voice cues turned
    off in settings."""
    queue = InsightQueue()
    queue.publish([_insight("br.late")])

    vm = CoachingCardViewModel(queue=queue, audio_player=None)
    vm.poll()
    vm.dismiss()  # exercise both paths

    # No assertion needed — we're verifying nothing raised.


def test_audio_player_default_is_none() -> None:
    """``audio_player`` defaults to ``None`` so existing T091/T092
    callers (which don't pass one) keep working unchanged."""
    queue = InsightQueue()
    queue.publish([_insight("br.late")])

    # Construct without audio_player kwarg — must succeed
    vm = CoachingCardViewModel(queue=queue)
    vm.poll()  # must not raise
