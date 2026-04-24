"""Coaching live processor (sprint T003).

Composes the existing ``live_detectors.DetectorManager`` and
``live_coach.LiveCoachTracker`` primitives behind the
``LiveProcessor`` ABC so ``LiveTelemetryProcessor`` (T006) can fan
events to coaching uniformly.

Produces two outputs per snapshot:

* ``notes`` — raw ``CoachingNote``s from the detector manager, one
  per detected event this sample cycle.
* ``cards`` — pre-formatted coaching card dicts derived from the
  live coach tracker's alert / prompt streams, compatible with the
  overlay ``CoachingCardViewModel``.
"""

from __future__ import annotations

import os
from typing import Any

from lap_coach_logger.core.detector_models import CoachingNote, DetectorConfig
from lap_coach_logger.core.live_coach import LiveCoachTracker
from lap_coach_logger.core.live_detectors import DetectorManager
from lap_coach_logger.core.live_processor import LiveProcessor
from lap_coach_logger.core.schema import TelemetrySample


_FEATURE_FLAG = "LIVE_COACHING_ENABLED"
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _flag_enabled() -> bool:
    raw = os.environ.get(_FEATURE_FLAG)
    if raw is None:
        return True
    return raw.strip().lower() not in _FALSE_VALUES


class CoachingLiveProcessor(LiveProcessor):
    """Live coaching sub-processor built on ``DetectorManager`` + ``LiveCoachTracker``.

    Respects the ``LIVE_COACHING_ENABLED`` environment flag: when false
    (``0``/``false``/``no``/``off``, case-insensitive), ``on_sample`` is
    a no-op and ``snapshot`` returns empty lists.
    """

    __slots__ = ("detector_manager", "_coach_tracker", "_pending_notes", "enabled")

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.detector_manager = DetectorManager(config)
        self._coach_tracker = LiveCoachTracker()
        self._pending_notes: list[CoachingNote] = []
        self.enabled = _flag_enabled()

    def on_sample(
        self,
        sample: TelemetrySample,
        *,
        dashboard_state: dict[str, Any] | None = None,
        derived_state: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return
        self._pending_notes = self.detector_manager.check(sample)
        self._coach_tracker.push_sample(
            sample,
            dashboard_state=dashboard_state,
            derived_state=derived_state,
        )

    def on_lap_end(self, lap_number: int, lap_time_s: float | None) -> None:
        # LiveCoachTracker finalizes laps on its own via sample lap_number
        # transitions; nothing to do here. Hook retained for the ABC.
        return None

    def on_session_end(self) -> None:
        self.detector_manager.reset()
        self._coach_tracker.reset()
        self._pending_notes = []

    def snapshot(self) -> dict[str, Any]:
        if not self.enabled:
            return {"notes": [], "cards": []}
        coach_snap = self._coach_tracker.snapshot()
        alerts = coach_snap.get("alerts", []) or []
        prompts = coach_snap.get("coaching", []) or []
        return {
            "notes": list(self._pending_notes),
            "cards": _build_coaching_cards(alerts, prompts),
        }


def _build_coaching_cards(
    alerts: list[dict[str, Any]], prompts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for alert in alerts:
        severity = str(alert.get("severity", "caution"))
        if severity == "error":
            severity = "critical"
        cards.append({
            "headline": str(alert.get("title", "")),
            "sub": str(alert.get("detail", "")),
            "category": "ALERT",
            "severity": severity,
            "confidence": 90,
            "sector": "",
        })
    for prompt in prompts:
        cards.append({
            "headline": str(prompt.get("title", "")),
            "sub": str(prompt.get("detail", "")),
            "category": "COACHING",
            "severity": "caution",
            "confidence": 80,
            "sector": str(prompt.get("corner", "")),
        })
    return cards


__all__ = ["CoachingLiveProcessor"]
