"""T091: Overlay-card ViewModel that consumes the rules-engine
insight stream.

Wires the rules engine (T080's CoachingInsight, T082's
InsightQueue, T083's emit_lap_insights) to QML's binding model:

    LiveTelemetryProcessor.emit_lap_insights  (sample thread)
                  ↓
              InsightQueue                     (thread-safe)
                  ↓
            CoachingCardViewModel.poll()       (Qt main thread)
                  ↓
              QML bindings on .insight

Polling cadence is owned by Qt externally — typically a QTimer
ticking once per second. The VM doesn't own the timer because
test setups don't have one and shouldn't need one.

This VM is deliberately minimal. Cooldown, skill-level variants,
animations, dismiss/flag UX — those are T092 / T093 / T094 /
T095 / T096 / T097 / T098, downstream tasks.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Callable

from PySide6.QtCore import Property, QObject, Signal, Slot

from lap_coach_logger.coaching.rules_engine import (
    CoachingInsight,
    InsightCooldownFilter,
    InsightQueue,
)


class CoachingCardViewModel(QObject):
    """QML-bindable view of the current coaching insight."""

    insightChanged = Signal()

    def __init__(
        self,
        *,
        queue: InsightQueue,
        cooldown_filter: InsightCooldownFilter | None = None,
        skill_level: str = "intermediate",
        audio_player: Callable[[CoachingInsight], None] | None = None,
        flag_callback: Callable[[CoachingInsight, str], None] | None = None,
        enabled: bool = True,
    ) -> None:
        super().__init__()
        self._queue = queue
        # T103: feature flag. False ⇒ poll drains queue but
        # surfaces nothing; dismiss / flag are safe no-ops.
        # Read at session start; mid-session toggling is out
        # of scope (matches T093 / T096 / T098 decision).
        self._enabled = enabled
        # T092: optional cooldown filter. None = no cooldown
        # (T091 tests; production wiring passes a 30s filter).
        self._cooldown_filter = cooldown_filter
        # T093: which skill_levels variant to surface as
        # insight.text. Default mirrors the coaching library's
        # authoring guidance — most users are intermediate.
        self._skill_level = skill_level
        # T096: optional audio cue. None = silent. Callback
        # receives the CoachingInsight when it becomes the
        # current card (poll integrates it, or dismiss advances
        # to it). Configurable via the user's "Enable voice
        # cues" setting — bootstrap reads the setting and
        # passes either a real player or None.
        self._audio_player = audio_player
        # T098: optional flag-as-wrong callback. None = local
        # only (dismiss but don't ship to backend). Callback
        # signature is ``(insight, reason)`` — production wiring
        # composes a real HTTP-POST closure; tests inject a
        # capturing list-append.
        self._flag_callback = flag_callback
        self._current: CoachingInsight | None = None
        self._pending: deque[CoachingInsight] = deque()

    # -- QML properties --------------------------------------------------------

    @Property("QVariant", notify=insightChanged)
    def insight(self) -> dict[str, Any]:
        """The currently-shown insight as a dict, or ``{}`` when
        nothing is shown. QML reads ``vm.insight.title``,
        ``vm.insight.text``, etc.

        T093: ``text`` is derived from the rule's
        ``skill_levels`` dict using the VM's configured
        ``skill_level``, falling back to ``title`` and finally
        ``""``. Other payload fields pass through unchanged.
        """
        if self._current is None:
            return {}
        payload = self._current.payload
        skill_levels = payload.get("skill_levels")
        if isinstance(skill_levels, dict) and self._skill_level in skill_levels:
            text = skill_levels[self._skill_level]
        else:
            text = payload.get("title", "")
        return {
            "rule_id": self._current.rule_id,
            **payload,
            "text": text,
        }

    @Property(bool, notify=insightChanged)
    def has_insight(self) -> bool:
        """``True`` when an insight is currently shown — drives
        the QML card's ``visible`` binding."""
        return self._current is not None

    # -- slots (QML / external callable) ---------------------------------------

    @Slot()
    def poll(self) -> None:
        """Drain the queue and integrate any new insights.

        - First incoming insight when nothing is shown becomes
          the current insight; subsequent ones queue up.
        - Subsequent incoming insights when a card is already
          shown queue up behind it (FIFO).

        Empty drain ⇒ no signal emit (avoid pointless QML
        rebinds on every timer tick).

        T103: when the VM is disabled, drain the queue but
        surface nothing — keeps the queue from growing
        unboundedly while honouring the user's "off" setting.
        """
        new_insights = self._queue.drain()
        if not self._enabled:
            return  # drained but discarded
        if self._cooldown_filter is not None:
            new_insights = self._cooldown_filter.filter(new_insights)
        if not new_insights:
            return

        self._pending.extend(new_insights)
        was_empty = self._current is None
        if was_empty and self._pending:
            self._current = self._pending.popleft()
            self._maybe_play_audio_cue()
        self.insightChanged.emit()

    @Slot()
    def dismiss(self) -> None:
        """Clear the current insight and advance to the next
        pending one (if any). No-op when nothing is shown."""
        if self._current is None:
            return
        self._current = self._pending.popleft() if self._pending else None
        if self._current is not None:
            self._maybe_play_audio_cue()
        self.insightChanged.emit()

    @Slot(str)
    def flag_as_wrong(self, reason: str) -> None:  # noqa: N802
        """User flagged the current insight as wrong / not
        applicable. Forwards ``(insight, reason)`` to the
        configured callback (if any) and dismisses the card.

        No-op when nothing's currently shown — guards against
        a stale QML rebind firing flag during a fade-out. The
        backend POST + the dismiss are independent: a None
        callback still dismisses so the local UX stays
        responsive.
        """
        if self._current is None:
            return
        if self._flag_callback is not None:
            self._flag_callback(self._current, reason)
        self.dismiss()

    # -- internals -------------------------------------------------------------

    def _maybe_play_audio_cue(self) -> None:
        """Fire the configured audio cue for the current insight.
        Always called when ``_current`` just became non-None."""
        if self._audio_player is None or self._current is None:
            return
        self._audio_player(self._current)


__all__ = ["CoachingCardViewModel"]
