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
from typing import Any

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
    ) -> None:
        super().__init__()
        self._queue = queue
        # T092: optional cooldown filter. None = no cooldown
        # (T091 tests; production wiring passes a 30s filter).
        self._cooldown_filter = cooldown_filter
        # T093: which skill_levels variant to surface as
        # insight.text. Default mirrors the coaching library's
        # authoring guidance — most users are intermediate.
        self._skill_level = skill_level
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
        rebinds on every timer tick)."""
        new_insights = self._queue.drain()
        if self._cooldown_filter is not None:
            new_insights = self._cooldown_filter.filter(new_insights)
        if not new_insights:
            return

        self._pending.extend(new_insights)
        if self._current is None and self._pending:
            self._current = self._pending.popleft()
        self.insightChanged.emit()

    @Slot()
    def dismiss(self) -> None:
        """Clear the current insight and advance to the next
        pending one (if any). No-op when nothing is shown."""
        if self._current is None:
            return
        self._current = self._pending.popleft() if self._pending else None
        self.insightChanged.emit()


__all__ = ["CoachingCardViewModel"]
