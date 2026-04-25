"""T098: "Flag as wrong" button on the coaching card.

User taps "flag" → VM forwards the insight + reason to a
configured callback that POSTs to the backend feedback endpoint.
After flagging, the card dismisses automatically (the user
didn't agree with the tip; show them the next one or hide the
card).

Why a callback (not an HTTP client baked into the VM):
- The VM should not own urlopen / Bearer-token plumbing —
  that's the IngestClient / RuleBundleHttpClient pattern,
  injected at construction time.
- Tests can capture the callback args without spinning up a
  hermetic HTTP server (ThreadingHTTPServer is fine but
  overkill for "did the VM forward the right insight?").

Backend isn't live for the feedback endpoint yet, but the
client-side wiring lands here per the established pattern
(T042-T055 ingest-client work shipped hermetically; backend
catches up).

Production wiring will compose:
  flag_callback = lambda insight, reason: feedback_client.flag(
      insight=insight, reason=reason, auth_token=...
  )
And tests can substitute a list-appending capture.
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
# flag_as_wrong: forwards to callback, dismisses card
# ---------------------------------------------------------------------------


def test_flag_callback_receives_current_insight_and_reason() -> None:
    """The callback signature is ``(insight, reason)`` so the
    backend gets both the rule that fired AND the user's
    optional explanatory note. T098 doesn't ship a free-text
    UI yet — the QML button passes a default reason — so the
    test uses an explicit one to pin the call shape."""
    queue = InsightQueue()
    queue.publish([_insight("br.late")])
    flagged: list[tuple[CoachingInsight, str]] = []

    vm = CoachingCardViewModel(
        queue=queue, flag_callback=lambda i, r: flagged.append((i, r))
    )
    vm.poll()

    vm.flag_as_wrong("user_flagged_from_card")

    assert len(flagged) == 1
    assert flagged[0][0].rule_id == "br.late"
    assert flagged[0][1] == "user_flagged_from_card"


def test_flag_as_wrong_dismisses_current_insight() -> None:
    """Flagging implies "I disagree with this tip" — the user
    doesn't want to see it linger. After flag, the VM advances
    to the next pending insight (or clears if none queued).

    Equivalent to the user pressing dismiss after typing their
    flag reason — saves them a click, matches the user
    expectation that "I'm done with this card"."""
    queue = InsightQueue()
    queue.publish([_insight("br.late"), _insight("ac.apex_loss")])

    vm = CoachingCardViewModel(queue=queue, flag_callback=lambda i, r: None)
    vm.poll()  # current = br.late

    vm.flag_as_wrong("doesnt_apply")

    # Dismissed → advanced to next pending
    assert vm.insight["rule_id"] == "ac.apex_loss"


def test_flag_as_wrong_with_no_current_is_a_noop() -> None:
    """User clicks the (somehow stale) flag button on an empty
    card — must not call the callback, must not raise. Without
    this, an over-eager rebind in QML during a fade-out could
    fire a flag for a no-longer-current insight."""
    queue = InsightQueue()
    flagged: list[tuple[CoachingInsight, str]] = []

    vm = CoachingCardViewModel(
        queue=queue, flag_callback=lambda i, r: flagged.append((i, r))
    )
    # No poll, no insight → no current

    vm.flag_as_wrong("user_flagged")

    assert flagged == []


# ---------------------------------------------------------------------------
# Configurability — None opts out
# ---------------------------------------------------------------------------


def test_flag_callback_none_means_local_only() -> None:
    """``flag_callback=None`` is the explicit "don't ship to
    backend" config. Useful for tests, demo mode, or environments
    without network. Must still dismiss the card so the local
    UX still feels responsive."""
    queue = InsightQueue()
    queue.publish([_insight("br.late"), _insight("ac.apex_loss")])

    vm = CoachingCardViewModel(queue=queue, flag_callback=None)
    vm.poll()

    vm.flag_as_wrong("doesnt_apply")  # must not raise

    # Card still dismissed even though no callback fired
    assert vm.insight["rule_id"] == "ac.apex_loss"


def test_flag_callback_default_is_none() -> None:
    """Backwards compat — T091/T092/T093/T096 callers don't pass
    flag_callback; they should keep working unchanged."""
    queue = InsightQueue()
    queue.publish([_insight("br.late")])

    # Construct without flag_callback kwarg — must succeed
    vm = CoachingCardViewModel(queue=queue)
    vm.poll()
    vm.flag_as_wrong("test")  # must not raise


# ---------------------------------------------------------------------------
# Integration: flag does not interfere with audio cues
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# QML widget wiring
# ---------------------------------------------------------------------------


def test_qml_widget_invokes_flag_as_wrong_with_a_reason() -> None:
    """The QML "flag" button must call ``flag_as_wrong`` with a
    reason string (not zero-arg). Pinning prevents a refactor
    that drops the reason arg from going unnoticed — the
    backend would lose the signal even though the button still
    visibly works."""
    from pathlib import Path

    qml_path = (
        Path(__file__).resolve().parents[1]
        / "src" / "lap_coach_logger" / "qml" / "Components" / "CoachingCard.qml"
    )
    qml = qml_path.read_text(encoding="utf-8")

    # Match a call with a non-empty argument: flag_as_wrong("...")
    import re
    match = re.search(
        r"coachingCardVM\.flag_as_wrong\(\"[^\"]+\"\)", qml
    )
    assert match is not None, (
        "QML must invoke flag_as_wrong(<reason>) with a non-empty "
        "reason string"
    )


def test_qml_widget_has_flag_button_glyph() -> None:
    from pathlib import Path

    qml_path = (
        Path(__file__).resolve().parents[1]
        / "src" / "lap_coach_logger" / "qml" / "Components" / "CoachingCard.qml"
    )
    qml = qml_path.read_text(encoding="utf-8")
    assert any(glyph in qml for glyph in ("⚑", "⚐", "🚩", "Flag"))


def test_flag_advancing_to_next_fires_audio_cue() -> None:
    """When flag dismisses the current card and advances to the
    next pending one, the audio cue (T096) should fire — same
    behaviour as a plain dismiss(). The user heard the cue
    because a NEW insight just appeared, regardless of why the
    previous one went away."""
    queue = InsightQueue()
    queue.publish([_insight("br.late"), _insight("ac.apex_loss")])
    cued: list[CoachingInsight] = []

    vm = CoachingCardViewModel(
        queue=queue,
        flag_callback=lambda i, r: None,
        audio_player=cued.append,
    )
    vm.poll()  # cues br.late
    cued.clear()

    vm.flag_as_wrong("test")  # advances → cues ac.apex_loss

    assert [i.rule_id for i in cued] == ["ac.apex_loss"]
