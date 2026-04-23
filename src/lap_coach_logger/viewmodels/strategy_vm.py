"""StrategyViewModel -- QObject bridge between strategy engine and QML."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot

from lap_coach_logger.coaching.corner_insights import CornerInsight
from lap_coach_logger.coaching.plan_engine import CoachingPlan, generate_plan
from lap_coach_logger.coaching.plan_evaluator import PlanResult, evaluate_plan
from lap_coach_logger.coaching.post_session_summary import (
    build_post_session_summary,
    summary_to_dict,
)
from lap_coach_logger.coaching.policy_config import (
    COACHING_TAB_POLICY,
    DEFAULT_POLICY,
    PolicyConfig,
)
from lap_coach_logger.coaching.presentation import (
    CoachingMessage,
    message_from_plan,
    message_from_summary,
    message_to_dict,
)
from lap_coach_logger.coaching.strategy_review import (
    build_strategy_review,
    review_to_dict,
)
from lap_coach_logger.coaching.readiness import assess_readiness
from lap_coach_logger.core.consistency_analyzer import ConsistencyReport, analyze_consistency
from lap_coach_logger.core.metric_state import MetricState, classify_metric
from lap_coach_logger.data_mode.inspector import (
    InspectionReport,
    inspect_channels,
)
from lap_coach_logger.core.practice_readiness import (
    compute_nudges,
    compute_race_statistics,
    compute_readiness,
)
from lap_coach_logger.core.mode_descriptor import get_mode
from lap_coach_logger.core.race_strategy import (
    ConditionWindow,
    PlannedStint,
    RacePlan,
    optimize_strategy,
    recalculate_live_plan,
)
from lap_coach_logger.core.stint_recorder import StintRecorder
from lap_coach_logger.core.stint_store import CompoundProfile, StintStore
from lap_coach_logger.core.strategy_models import PitProfile  # noqa: F401
from lap_coach_logger.normalization.resolver import CanonicalResolver
from lap_coach_logger.sync.queue import SyncQueue
from lap_coach_logger.sync.schema import (
    CoachingPayload,
    EventPayload,
    LapPayload,
    SessionPayload,
    SyncEnvelope,
)
from lap_coach_logger.utils.qt_safe_slot import safe_slot
from lap_coach_logger.utils.snapshot_validator import safe_get, validate_live

log = logging.getLogger(__name__)


class StrategyViewModel(QObject):
    """Exposes strategy data to QML via Properties and Slots."""

    # -- change signals --------------------------------------------------------
    profilesChanged = Signal()
    planChanged = Signal()
    stintLogChanged = Signal()
    alertsChanged = Signal()
    recordingChanged = Signal()
    weatherChanged = Signal()

    # -- construction ----------------------------------------------------------

    def __init__(self, store: StintStore, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._track = ""
        self._car = ""
        self._car_class = ""                # resolved via LUT, drives per-class calibration
        self._sim_id = ""                   # last-seen sim_id from telemetry
        self._resolver: CanonicalResolver | None = None
        self._total_laps = 0
        self._fuel_capacity = 0.0
        self._pit_time = 25.0
        self._profiles: dict[str, CompoundProfile] = {}
        self._plan: RacePlan | None = None
        self._recorder: StintRecorder | None = None
        self._conditions: list[ConditionWindow] = []
        self._race_mode = "laps"
        self._race_duration_hours = 0.0
        self._was_in_pits = False
        self._mode = "sprint"
        self._lap_times_buffer: list[float] = []
        self._prev_consistency_lap = 0
        self._prev_consistency_time: float | None = None
        self._active_plan: CoachingPlan | None = None
        self._last_plan_result: PlanResult | None = None
        self._laps_since_plan: int = 0
        self._pre_plan_lap_times: list[float] = []
        # Corner-level technique coaching (sprint):
        # - latest: insights from the lap that just finalized
        # - history: per-lap list; used for post-session summary + blocker
        #   classification.
        self._corner_insights_latest: list[CornerInsight] = []
        self._corner_insights_history: list[list[CornerInsight]] = []
        # -- Live strategy recalculation (redesign v2) --------------------------
        self._fuel_deltas: list[float] = []         # per-lap fuel consumption
        self._prev_fuel_level: float | None = None   # last-known fuel for delta calc
        self._current_fuel: float = 0.0              # latest fuel reading
        self._race_active = False                     # True after green flag in race session
        self._original_plan: RacePlan | None = None   # frozen pre-race plan for plan-vs-actual
        self._actual_pit_laps: list[int] = []         # recorded pit entry laps
        self._actual_fuel_added: list[float] = []     # fuel added at each actual stop
        # -- Sync wiring -------------------------------------------------------
        self._sync_queue: SyncQueue | None = None
        self._session_id: str = ""
        self._session_started_at: str = ""
        self._last_synced_lap: int = 0
        # -- Data mode inspection buffer --------------------------------------
        self._snapshot_buffer: list[dict] = []
        self._snapshot_buffer_max = 500  # rolling window for inspection
        self._sample_rate_hz: float = 0.0
        self._last_snapshot_time: float | None = None

    # -- Sync setter (called from bootstrap wiring) ---------------------------

    def set_sync_queue(self, queue: SyncQueue) -> None:
        """Inject the sync queue. Not a Slot -- called once at startup."""
        self._sync_queue = queue

    # -- QML properties --------------------------------------------------------

    @Property(str, notify=profilesChanged)
    def trackName(self) -> str:  # noqa: N802
        return self._track

    @Property(str, notify=profilesChanged)
    def carName(self) -> str:  # noqa: N802
        return self._car

    @Property(str, notify=profilesChanged)
    def carClass(self) -> str:  # noqa: N802
        """Canonical car class (e.g. "GT3", "LMP2").

        Resolved via CanonicalResolver from (sim_id, raw_car) on first
        snapshot and whenever the car changes. Empty string when the LUT
        has no entry — overlay code treats empty as "use GT3 defaults".
        """
        return self._car_class

    @Property(int, notify=planChanged)
    def totalLaps(self) -> int:  # noqa: N802
        return self._total_laps

    @Property(float, notify=planChanged)
    def fuelCapacity(self) -> float:  # noqa: N802
        return self._fuel_capacity

    @Property(float, notify=planChanged)
    def pitTime(self) -> float:  # noqa: N802
        return self._pit_time

    @Property(list, notify=profilesChanged)
    def compoundProfiles(self) -> list[dict[str, Any]]:  # noqa: N802
        return [p.to_dict() for p in self._profiles.values()]

    @Property(list, notify=planChanged)
    def racePlan(self) -> list[dict[str, Any]]:  # noqa: N802
        if self._plan is None:
            return []
        return [
            {
                "compound": s.compound,
                "start_lap": s.start_lap,
                "end_lap": s.end_lap,
                "fuel_at_start": round(s.fuel_at_start, 1),
                "fuel_to_add": round(s.fuel_to_add, 1),
                "grip_at_end": round(s.grip_at_end, 1),
                "estimated_time_s": round(s.estimated_time_s, 1),
            }
            for s in self._plan.stints
        ]

    @Property(list, notify=stintLogChanged)
    def stintLog(self) -> list[dict[str, Any]]:  # noqa: N802
        return [s.to_dict() for s in self._store.list_stints(self._track, self._car)]

    @Property(list, notify=alertsChanged)
    def alerts(self) -> list[dict[str, Any]]:
        if self._plan is None:
            return []
        return [
            {
                "severity": a.severity,
                "category": a.category,
                "message": a.message,
                "suggested_action": a.suggested_action,
            }
            for a in self._plan.alerts
        ]

    @Property(bool, notify=recordingChanged)
    def isRecording(self) -> bool:  # noqa: N802
        return self._recorder is not None and self._recorder.is_recording

    @Property(bool, notify=weatherChanged)
    def hasWeatherData(self) -> bool:  # noqa: N802
        return len(self._conditions) > 0

    @Property(list, notify=weatherChanged)
    def weatherTimeline(self) -> list[dict[str, Any]]:  # noqa: N802
        return [
            {
                "start_lap": w.start_lap,
                "end_lap": w.end_lap,
                "track_temp_c": w.track_temp_c,
                "precipitation": w.precipitation,
                "track_state": w.track_state,
                "recommended_compound": w.recommended_compound,
            }
            for w in self._conditions
        ]

    @Property(bool, notify=alertsChanged)
    def planDiverged(self) -> bool:  # noqa: N802
        if self._plan is None:
            return False
        return any(a.category == "divergence" for a in self._plan.alerts)

    @Property(float, notify=planChanged)
    def planFuelAtFinish(self) -> float:  # noqa: N802
        return self._plan.fuel_at_finish if self._plan else 0.0

    @Property(float, notify=planChanged)
    def planTotalTime(self) -> float:  # noqa: N802
        return self._plan.total_race_time_s if self._plan else 0.0

    @Property(int, notify=planChanged)
    def planNumStops(self) -> int:  # noqa: N802
        return self._plan.num_stops if self._plan else 0

    # -- Live strategy properties (redesign v2) --------------------------------

    @Property(int, notify=alertsChanged)
    def lapsToPit(self) -> int:  # noqa: N802
        """Laps remaining until next planned pit stop. -1 if no plan or no remaining stops."""
        if not self._plan or not self._plan.next_pit_lap:
            return -1
        return max(0, self._plan.next_pit_lap - self._prev_consistency_lap)

    @Property(bool, notify=alertsChanged)
    def pitNow(self) -> bool:  # noqa: N802
        """True when the driver should pit THIS lap."""
        return self.lapsToPit == 1

    @Property(float, notify=alertsChanged)
    def pitFuelLoad(self) -> float:  # noqa: N802
        """Fuel to add at the next planned stop (liters)."""
        if not self._plan or not self._plan.stints:
            return 0.0
        # Find the next stint that hasn't started yet
        current = self._prev_consistency_lap
        for stint in self._plan.stints:
            if stint.start_lap > current:
                return stint.fuel_to_add
        return 0.0

    @Property(float, notify=alertsChanged)
    def fuelBurnRate(self) -> float:  # noqa: N802
        """Rolling 3-lap average fuel consumption (L/lap). 0 if insufficient data."""
        if len(self._fuel_deltas) < 1:
            return 0.0
        recent = self._fuel_deltas[-3:] if len(self._fuel_deltas) >= 3 else self._fuel_deltas
        return round(sum(recent) / len(recent), 3)

    @Property(float, notify=alertsChanged)
    def fuelMargin(self) -> float:  # noqa: N802
        """Fuel remaining minus fuel needed to finish (liters). Negative = deficit."""
        burn = self.fuelBurnRate
        if burn <= 0 or self._total_laps <= 0:
            return 0.0
        remaining_laps = max(0, self._total_laps - self._prev_consistency_lap)
        needed = remaining_laps * burn
        return round(self._current_fuel - needed, 2)

    @Property(bool, notify=alertsChanged)
    def strategyOnTrack(self) -> bool:  # noqa: N802
        """True when all divergence metrics are within acceptable bounds."""
        if not self._plan:
            return True
        return not any(
            a.category == "divergence" and a.severity in ("warning", "critical")
            for a in self._plan.alerts
        )

    @Property(int, notify=alertsChanged)
    def currentStintLap(self) -> int:  # noqa: N802
        """Lap within the current stint (1-indexed). 0 when unknown.

        Computed from the live plan — reflects stint shifts from the
        live recalc, not legacy tire-lap counters.
        """
        if self._plan is None or not self._plan.stints:
            return 0
        current = self._prev_consistency_lap
        if current <= 0:
            return 0
        for stint in self._plan.stints:
            if stint.start_lap <= current <= stint.end_lap:
                return current - stint.start_lap + 1
        return 0

    @Property(int, notify=alertsChanged)
    def currentStintTotalLaps(self) -> int:  # noqa: N802
        """Total planned laps for the current stint. 0 when unknown."""
        if self._plan is None or not self._plan.stints:
            return 0
        current = self._prev_consistency_lap
        if current <= 0:
            return 0
        for stint in self._plan.stints:
            if stint.start_lap <= current <= stint.end_lap:
                return stint.end_lap - stint.start_lap + 1
        return 0

    @Property("QVariant", notify=alertsChanged)
    def planVsActual(self) -> dict:  # noqa: N802
        """Raw planned-vs-actual structural data (stops, fuel, times).

        User-facing verdict / wording lives on ``strategyReview`` — QML
        must bind the review card to that property, not to raw fields
        here. This property is retained for structural debug / export.
        """
        if not self._original_plan:
            return {}
        planned_pit_laps = []
        for i, stint in enumerate(self._original_plan.stints[:-1]):
            planned_pit_laps.append(stint.end_lap)
        return {
            "planned_pit_laps": planned_pit_laps,
            "actual_pit_laps": self._actual_pit_laps,
            "planned_fuel_at_finish": self._original_plan.fuel_at_finish,
            "actual_fuel_at_finish": self._current_fuel,
            "planned_total_time": self._original_plan.total_race_time_s,
            "planned_num_stops": self._original_plan.num_stops,
            "actual_num_stops": len(self._actual_pit_laps),
            "fuel_deltas": self._fuel_deltas,
        }

    @Property(str, notify=planChanged)
    def raceMode(self) -> str:  # noqa: N802
        return self._race_mode

    @Property(float, notify=planChanged)
    def raceDurationHours(self) -> float:  # noqa: N802
        return self._race_duration_hours

    @Property("QVariant", notify=profilesChanged)
    def modelAvailability(self) -> dict[str, Any]:  # noqa: N802
        """Per-compound model availability for UI indicators."""
        result: dict[str, Any] = {}
        for compound, profile in self._profiles.items():
            result[compound] = {
                "thermal": profile.thermal is not None
                and profile.thermal.get("available", False),
                "warmup": profile.warmup is not None
                and profile.warmup.get("fitted", False),
                "degradation": profile.degradation is not None
                and profile.degradation.get("available", False),
                "total_laps_logged": profile.total_laps_logged,
                "stint_count": profile.stint_count,
            }
        return result

    @Property("QVariant", notify=profilesChanged)
    def readiness(self) -> dict:
        pit = self._store.get_pit_profile(self._track) if self._track else None
        return compute_readiness(self._profiles, pit)

    @Property(list, notify=profilesChanged)
    def nudges(self) -> list:
        pit = self._store.get_pit_profile(self._track) if self._track else None
        compounds = list(self._profiles.keys()) or ["soft", "medium", "hard"]
        return compute_nudges(self._profiles, pit, compounds)

    @Property("QVariant", notify=planChanged)
    def raceStatistics(self) -> dict:  # noqa: N802
        if self._plan is None:
            return {}
        return compute_race_statistics(
            self.racePlan, self._profiles, self._fuel_capacity,
            self._plan.total_race_time_s, self._plan.fuel_at_finish,
        )

    @Property("QVariant", notify=planChanged)
    def metricStates(self) -> dict[str, str]:  # noqa: N802
        """Confidence state for each key strategy metric."""
        return {
            "fuel_capacity": classify_metric(
                self._fuel_capacity if self._fuel_capacity > 0 else None
            ).value,
            "pit_time": classify_metric(
                self._pit_time if self._pit_time != 25.0 else None,
                is_derived=self._pit_time == 25.0,
            ).value,
            "fuel_per_lap": classify_metric(
                next((p.fuel_per_lap for p in self._profiles.values()), None)
            ).value,
            "total_laps": classify_metric(
                self._total_laps if self._total_laps > 0 else None
            ).value,
        }

    @Property("QVariant", notify=profilesChanged)
    def consistencyReport(self) -> dict:  # noqa: N802
        report = analyze_consistency(self._lap_times_buffer)
        if report is None:
            return {}
        return report.to_dict()

    @Property("QVariant", notify=profilesChanged)
    def activePlan(self) -> dict:  # noqa: N802
        """Current coaching focus plan with measurable target."""
        if self._active_plan is None:
            return {}
        return {
            "focus_area": self._active_plan.focus_area,
            "objective": self._active_plan.objective,
            "measurable_target": self._active_plan.measurable_target,
            "ignore_list": list(self._active_plan.ignore_list),
            "evaluation_window": self._active_plan.evaluation_window,
            "confidence": self._active_plan.confidence.value,
            "reason": self._active_plan.reason,
            "technique_insight": self._active_plan.technique_insight,
            "corner_focus": self._active_plan.corner_focus,
            "technique_action": self._active_plan.technique_action,
            "likely_cause": self._active_plan.likely_cause,
            "laps_remaining": max(
                0, self._active_plan.evaluation_window - self._laps_since_plan
            ),
        }

    # -- Unified coaching presentation (Coaching Surface Unification) --------

    def build_coaching_message(
        self,
        config: PolicyConfig = DEFAULT_POLICY,
    ) -> CoachingMessage:
        """Build the unified CoachingMessage directly (no dict round-trip).

        Overlay VM + Coaching tab both call this with their own
        ``PolicyConfig`` — identical source fields, surface-specific
        truncation. Prefers the plan's ``plan_time_loss_s`` snapshot
        over the latest lap's (stable across the plan lifetime) and
        falls back to the insights list only when the plan predates
        that field.
        """
        plan = self._active_plan
        if plan is None:
            return CoachingMessage()
        time_loss = plan.plan_time_loss_s
        if time_loss is None and plan.corner_focus:
            time_loss = next(
                (
                    i.time_loss_s for i in self._corner_insights_latest
                    if i.corner_name == plan.corner_focus
                ),
                None,
            )
        return message_from_plan(plan, time_loss_s=time_loss, config=config)

    @Property("QVariant", notify=profilesChanged)
    def coachingMessage(self) -> dict:  # noqa: N802
        """The unified coaching message dict for the Coaching tab.

        Uses ``COACHING_TAB_POLICY`` so the tab can show richer text
        than the overlay while the underlying content (focus, action,
        confidence, category) is guaranteed to match — same contract,
        same source fields, different truncation limits only.
        """
        return message_to_dict(self.build_coaching_message(config=COACHING_TAB_POLICY))

    @Property("QVariant", notify=profilesChanged)
    def postSessionMessage(self) -> dict:  # noqa: N802
        """Post-session summary in the unified coaching message shape."""
        summary = build_post_session_summary(self._corner_insights_history)
        return message_to_dict(message_from_summary(summary))

    @Property("QVariant", notify=profilesChanged)
    def strategyReview(self) -> dict:  # noqa: N802
        """Post-session strategy verdict — compact "did I follow the plan?".

        Returns a dict with verdict, planned/actual stop counts, biggest
        divergence classification, fuel variance, next-time suggestion,
        and pre-formatted rows for the review card. Degraded when no
        plan exists or data is insufficient.
        """
        review = build_strategy_review(
            original_plan=self._original_plan,
            actual_pit_laps=list(self._actual_pit_laps),
            actual_fuel_added=list(self._actual_fuel_added),
            final_fuel_l=self._current_fuel,
        )
        return review_to_dict(review)

    # -- Corner-level technique coaching (sprint) -----------------------------

    @Property(str, notify=profilesChanged)
    def cornerFocus(self) -> str:  # noqa: N802
        """Name of the corner the coaching plan is focused on. Empty
        string when the plan is sector-level or not yet generated."""
        return self._active_plan.corner_focus if self._active_plan else ""

    @Property(str, notify=profilesChanged)
    def techniqueInsight(self) -> str:  # noqa: N802
        """Concrete, data-driven coaching statement for the focus area.

        Routed through ``build_coaching_message`` so the Coaching tab
        sees the same headline text the overlay surface does (just
        governed by ``COACHING_TAB_POLICY`` — longer limits, same source).
        """
        return self.build_coaching_message(config=COACHING_TAB_POLICY).headline

    @Property(str, notify=profilesChanged)
    def techniqueAction(self) -> str:  # noqa: N802
        """One-line action hint, governed by the shared contract."""
        return self.build_coaching_message(config=COACHING_TAB_POLICY).subline

    @Property(str, notify=profilesChanged)
    def techniqueConfidence(self) -> str:  # noqa: N802
        """Confidence for the technique insight: high/medium/low."""
        return self.build_coaching_message(config=COACHING_TAB_POLICY).confidence

    @Property(list, notify=profilesChanged)
    def cornerInsights(self) -> list:  # noqa: N802
        """Latest per-corner insight list for diagnostics/tests."""
        return [
            {
                "corner_name": i.corner_name,
                "time_loss_s": i.time_loss_s,
                "entry_speed_delta_kph": i.entry_speed_delta_kph,
                "min_speed_delta_kph": i.min_speed_delta_kph,
                "exit_speed_delta_kph": i.exit_speed_delta_kph,
                "brake_onset_delta_pct": i.brake_onset_delta_pct,
                "brake_release_delta_pct": i.brake_release_delta_pct,
                "throttle_pickup_delta_pct": i.throttle_pickup_delta_pct,
                "confidence": i.confidence,
                "loss_zone": i.loss_zone,
            }
            for i in self._corner_insights_latest
        ]

    # Rolling window for endurance sessions — 120 laps is ~3 hours at
    # 90s pace, a safe ceiling that preserves all realistic summary
    # signal while keeping memory bounded.
    _CORNER_INSIGHT_HISTORY_CAP = 120

    def push_corner_insights(self, insights: list[CornerInsight]) -> None:
        """Accept a fresh per-corner insight list from the live processor.

        Called by the overlay VM after each lap finalisation. Updates
        the history for post-session summary + readiness blocker
        classification, and triggers a UI refresh so the technique
        properties re-read on the next binding tick.
        """
        self._corner_insights_latest = list(insights)
        if insights:
            self._corner_insights_history.append(list(insights))
            if len(self._corner_insights_history) > self._CORNER_INSIGHT_HISTORY_CAP:
                self._corner_insights_history = self._corner_insights_history[
                    -self._CORNER_INSIGHT_HISTORY_CAP:
                ]
        self.profilesChanged.emit()

    @Property("QVariant", notify=profilesChanged)
    def postSessionSummary(self) -> dict:  # noqa: N802
        """Compact end-of-session coaching summary.

        Returns a dict with ``problem_zones`` (top 3 corners),
        ``largest_loss_area`` (single biggest time-on-table area), and
        ``primary_next_session_focus`` (one actionable sentence).
        Empty fields when insufficient data — see post_session_summary
        for the shape.
        """
        summary = build_post_session_summary(self._corner_insights_history)
        return summary_to_dict(summary)

    @Property("QVariant", notify=profilesChanged)
    def planResult(self) -> dict:  # noqa: N802
        """Result of the most recently evaluated plan."""
        if self._last_plan_result is None:
            return {}
        return {
            "success": self._last_plan_result.success,
            "delta_vs_target": self._last_plan_result.delta_vs_target,
            "updated_std_dev": self._last_plan_result.updated_std_dev,
            "next_action": self._last_plan_result.next_action,
            "confidence": self._last_plan_result.confidence.value,
            "reason": self._last_plan_result.reason,
        }

    @Property("QVariant", notify=profilesChanged)
    def readinessState(self) -> dict:  # noqa: N802
        """Race readiness assessment based on consistency."""
        report = analyze_consistency(self._lap_times_buffer)
        output = assess_readiness(report)
        assessment = output.value
        return {
            "state": assessment.state.value,
            "consistency_ok": assessment.consistency_ok,
            "variance_stable": assessment.variance_stable,
            "trend_ok": assessment.trend_ok,
            "no_outlier_corners": assessment.no_outlier_corners,
            "lap_count": assessment.lap_count,
            "confidence": output.confidence.value,
            "reason": output.reason,
        }

    @Property("QVariant", notify=profilesChanged)
    def paceBreakdown(self) -> dict:  # noqa: N802
        """Theoretical best and per-sector gains from consistency report."""
        report = analyze_consistency(self._lap_times_buffer)
        if report is None:
            return {}
        return {
            "best_lap_s": round(report.best_lap_time_s, 3),
            "median_lap_s": round(report.median_lap_time_s, 3),
            "theoretical_best_s": round(report.theoretical_best_s, 3),
            "gain_available_s": round(
                report.best_lap_time_s - report.theoretical_best_s, 3
            ),
            "per_sector_std_dev": [round(s, 3) for s in report.per_sector_std_dev],
            "worst_sector": report.worst_sector,
            "lap_count": report.lap_count,
        }

    @Property("QVariant", notify=profilesChanged)
    def syncStatus(self) -> dict:  # noqa: N802
        """Sync queue depth and state for UI display."""
        if self._sync_queue is None:
            return {"enabled": False, "queue_depth": 0, "session_id": ""}
        return {
            "enabled": True,
            "queue_depth": self._sync_queue.depth,
            "session_id": self._session_id,
        }

    @Property("QVariant", notify=profilesChanged)
    def dataInspection(self) -> dict:  # noqa: N802
        """Full channel inspection report for Data mode."""
        if not self._snapshot_buffer:
            return {
                "channels": [],
                "total_samples": 0,
                "sample_rate_hz": 0.0,
                "available_count": 0,
                "estimated_count": 0,
                "unavailable_count": 0,
                "warnings": ["No telemetry data yet"],
                "overall_quality": "poor",
            }
        report = inspect_channels(self._snapshot_buffer, self._sample_rate_hz)
        return report.to_dict()

    @Property(bool, notify=profilesChanged)
    def hasDataInspection(self) -> bool:  # noqa: N802
        return len(self._snapshot_buffer) > 0

    @Property(str, notify=planChanged)
    def currentMode(self) -> str:  # noqa: N802
        return self._mode

    @Property(list, notify=planChanged)
    def tabsForMode(self) -> list[dict]:  # noqa: N802
        return get_mode(self._mode).tab_dicts()

    @Property(str, notify=planChanged)
    def activeTab(self) -> str:  # noqa: N802
        return get_mode(self._mode).resolve_active_tab(
            has_plan=self._plan is not None,
            has_profiles=bool(self._profiles),
        )

    # -- Mode setter (called from bootstrap wiring) ----------------------------

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.planChanged.emit()

    # -- Slots -----------------------------------------------------------------

    @safe_slot()
    @Slot(str, str)
    def setTrackCar(self, track: str, car: str) -> None:  # noqa: N802
        self._track = track
        self._car = car
        self._profiles = self._store.get_profiles(track, car)
        # Re-resolve car class for the new car if sim is known.
        if self._sim_id and car:
            self._resolve_car_class(self._sim_id, car)
        self.profilesChanged.emit()
        self.stintLogChanged.emit()

    def _resolve_car_class(self, sim_id: str, raw_car: str) -> None:
        """Look up canonical car class via the LUT resolver, cache it.

        Emits profilesChanged when the resolved class actually changes
        so bound QML / overlay VM picks up the new calibration.
        """
        try:
            if self._resolver is None:
                self._resolver = CanonicalResolver()
            resolved = self._resolver.resolve_car(sim_id, raw_car)
            new_class = resolved.car_class or "" if resolved else ""
        except Exception:
            log.debug("Car class resolution failed", exc_info=True)
            new_class = ""
        if new_class != self._car_class:
            self._car_class = new_class
            log.info("Car class resolved: sim=%s car=%s -> %r", sim_id, raw_car, new_class)
            self.profilesChanged.emit()

    @safe_slot()
    @Slot(int)
    def setTotalLaps(self, n: int) -> None:  # noqa: N802
        self._total_laps = max(0, n)
        self.planChanged.emit()

    @safe_slot()
    @Slot(float)
    def setFuelCapacity(self, v: float) -> None:  # noqa: N802
        self._fuel_capacity = max(0, v)
        self.planChanged.emit()

    @safe_slot()
    @Slot(float)
    def setPitTime(self, v: float) -> None:  # noqa: N802
        self._pit_time = max(0, v)
        self.planChanged.emit()

    @safe_slot()
    @Slot(str)
    def setRaceMode(self, mode: str) -> None:  # noqa: N802
        if mode in ("laps", "timed"):
            self._race_mode = mode
            self.planChanged.emit()

    @safe_slot()
    @Slot(float)
    def setRaceDurationHours(self, hours: float) -> None:  # noqa: N802
        self._race_duration_hours = max(0.0, hours)
        self.planChanged.emit()

    @safe_slot()
    @Slot()
    def autoOptimize(self) -> None:  # noqa: N802
        if not self._profiles:
            return
        if self._race_mode == "laps" and self._total_laps <= 0:
            return
        if self._race_mode == "timed" and self._race_duration_hours <= 0:
            return

        pit_profile = self._store.get_pit_profile(self._track) if self._track else None

        self._plan = optimize_strategy(
            total_laps=self._total_laps,
            fuel_capacity=self._fuel_capacity,
            pit_time_s=self._pit_time,
            profiles=self._profiles,
            conditions=self._conditions or None,
            pit_profile=pit_profile,
            race_mode=self._race_mode,
            race_duration_s=self._race_duration_hours * 3600.0,
        )
        # Freeze original plan for post-race comparison
        self._original_plan = RacePlan(
            stints=list(self._plan.stints),
            total_race_time_s=self._plan.total_race_time_s,
            fuel_at_finish=self._plan.fuel_at_finish,
            alerts=[],
        )
        self._race_active = True
        self._fuel_deltas.clear()
        self._actual_pit_laps.clear()
        self._actual_fuel_added.clear()
        self.planChanged.emit()
        self.alertsChanged.emit()

    def _recalculate_live_strategy(self) -> None:
        """Recalculate strategy from current race position using actual data.

        Called once per completed lap during race modes. Uses measured
        fuel deltas and estimated tire wear to update the plan, generate
        divergence alerts, and update pit countdown state.
        """
        if self._plan is None:
            return
        try:
            pit_profile = self._store.get_pit_profile(self._track) if self._track else None
            # Estimate actual wear from stint lap count (simple linear proxy
            # from DegradationModel or fallback 2%/lap)
            current_stint_lap = self._prev_consistency_lap
            for stint in self._plan.stints:
                if stint.start_lap <= current_stint_lap <= stint.end_lap:
                    current_stint_lap = current_stint_lap - stint.start_lap + 1
                    break
            actual_wear = min(1.0, current_stint_lap * 0.02)  # fallback: 2%/lap

            self._plan = recalculate_live_plan(
                plan=self._plan,
                current_lap=self._prev_consistency_lap,
                current_fuel=self._current_fuel,
                actual_fuel_deltas=self._fuel_deltas,
                actual_wear=actual_wear,
                profiles=self._profiles,
                fuel_capacity=self._fuel_capacity,
                pit_time_s=self._pit_time,
                conditions=self._conditions or None,
                pit_profile=pit_profile,
            )
            self.planChanged.emit()
            self.alertsChanged.emit()
            log.debug(
                "Live strategy recalculated: lap=%d fuel=%.1fL margin=%.1fL pit_in=%d",
                self._prev_consistency_lap, self._current_fuel,
                self.fuelMargin, self.lapsToPit,
            )
        except Exception:
            log.warning("Live strategy recalculation failed", exc_info=True)

    @safe_slot()
    @Slot(str)
    def startRecording(self, compound: str) -> None:  # noqa: N802
        self._recorder = StintRecorder(
            store=self._store, track=self._track, car=self._car,
        )
        self._recorder.start(compound)
        self.recordingChanged.emit()

    @safe_slot()
    @Slot()
    def stopRecording(self) -> None:  # noqa: N802
        if self._recorder and self._recorder.is_recording:
            self._recorder.stop()
            self._profiles = self._store.get_profiles(self._track, self._car)
            self.profilesChanged.emit()
            self.stintLogChanged.emit()
        self.recordingChanged.emit()

    @safe_slot()
    @Slot(str)
    def excludeLoggedStint(self, stint_id: str) -> None:  # noqa: N802
        self._store.exclude_stint(stint_id)
        self._profiles = self._store.get_profiles(self._track, self._car)
        self.profilesChanged.emit()
        self.stintLogChanged.emit()

    @safe_slot()
    @Slot(str)
    def includeLoggedStint(self, stint_id: str) -> None:  # noqa: N802
        self._store.include_stint(stint_id)
        self._profiles = self._store.get_profiles(self._track, self._car)
        self.profilesChanged.emit()
        self.stintLogChanged.emit()

    @safe_slot()
    @Slot()
    def clearStints(self) -> None:  # noqa: N802
        self._store.clear(self._track, self._car)
        self._profiles = {}
        self.profilesChanged.emit()
        self.stintLogChanged.emit()

    @safe_slot()
    @Slot(result=str)
    def exportSessionJson(self) -> str:  # noqa: N802
        """Export current session snapshot to a JSON file. Returns the file path or empty string."""
        import json
        from datetime import datetime, timezone
        from pathlib import Path
        from lap_coach_logger.utils.paths import default_output_dir

        try:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"data_export_{ts}.json"
            out_path = default_output_dir() / filename
            payload = {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "track": self._track,
                "car": self._car,
                "mode": self._mode,
                "session_id": getattr(self, "_session_id", ""),
                "sample_count": len(self._snapshot_buffer),
                "sample_rate_hz": self._sample_rate_hz,
                "lap_times_s": list(self._lap_times_buffer),
                "inspection": self.dataInspection,
                "sync_status": self.syncStatus if hasattr(self, "syncStatus") else {},
            }
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            log.info("Exported session data to %s", out_path)
            return str(out_path)
        except Exception:
            log.exception("Failed to export session JSON")
            return ""

    # -- Auto-capture lifecycle ------------------------------------------------

    _AUTO_RECORD_SESSIONS = frozenset({
        "practice", "qualifying", "lone qualify", "open qualify",
    })

    def on_session_detected(self, session_type: str, track: str, car: str) -> None:
        """Called when a new session is detected from telemetry."""
        self.setTrackCar(track, car)
        self._lap_times_buffer = []
        self._prev_consistency_lap = 0
        self._prev_consistency_time = None
        self._active_plan = None
        self._last_plan_result = None
        self._laps_since_plan = 0
        self._pre_plan_lap_times = []
        self._snapshot_buffer = []
        self._sample_rate_hz = 0.0
        self._last_snapshot_time = None

        # Generate a new session_id and enqueue a SessionPayload
        self._session_id = str(uuid.uuid4())
        self._session_started_at = datetime.now(timezone.utc).isoformat()
        self._last_synced_lap = 0

        if self._sync_queue is not None:
            payload = SessionPayload(
                session_id=self._session_id,
                sim="unknown",  # enriched by the adapter layer once known
                track=track,
                car=car,
                mode=self._mode,
                start_time=self._session_started_at,
                end_time="",
            )
            # validate() returns [] when valid -- use "if not payload.validate()"
            if not payload.validate():
                envelope = SyncEnvelope(
                    payload_type="session",
                    payload=payload.to_dict(),
                )
                self._sync_queue.enqueue(envelope)

        if session_type.lower() in self._AUTO_RECORD_SESSIONS:
            self._recorder = StintRecorder(
                store=self._store, track=self._track, car=self._car,
            )
            self._recorder.start(compound="unknown")
        self.recordingChanged.emit()

    def on_pit_detected(self) -> None:
        """Called when the car enters the pit lane."""
        if self._recorder and self._recorder.is_recording:
            self._recorder.stop()
            self._profiles = self._store.get_profiles(self._track, self._car)
            self.profilesChanged.emit()
            self.stintLogChanged.emit()
        self._recorder = StintRecorder(
            store=self._store, track=self._track, car=self._car,
        )
        self._recorder.start(compound="unknown")
        self.recordingChanged.emit()

        # Emit pit_stop EventPayload
        if self._sync_queue is not None and self._session_id:
            event_payload = EventPayload(
                session_id=self._session_id,
                event_type="pit_stop",
                timestamp=datetime.now(timezone.utc).isoformat(),
                payload={"lap_number": self._prev_consistency_lap},
            )
            if not event_payload.validate():
                envelope = SyncEnvelope(
                    payload_type="event",
                    payload=event_payload.to_dict(),
                )
                self._sync_queue.enqueue(envelope)

    def on_session_ended(self) -> None:
        """Called when the session ends."""
        if self._recorder and self._recorder.is_recording:
            self._recorder.stop()
            self._profiles = self._store.get_profiles(self._track, self._car)
            self.profilesChanged.emit()
            self.stintLogChanged.emit()
        self._recorder = None
        self.recordingChanged.emit()

        # Emit final SessionPayload with end_time
        if self._sync_queue is not None and self._session_id:
            payload = SessionPayload(
                session_id=self._session_id,
                sim="unknown",
                track=self._track,
                car=self._car,
                mode=self._mode,
                start_time=self._session_started_at,
                end_time=datetime.now(timezone.utc).isoformat(),
            )
            if not payload.validate():
                envelope = SyncEnvelope(
                    payload_type="session_end",
                    payload=payload.to_dict(),
                )
                self._sync_queue.enqueue(envelope)

    @safe_slot()
    @Slot(int, int)
    def editStintLaps(self, index: int, laps: int) -> None:  # noqa: N802
        if self._plan is None or index < 0 or index >= len(self._plan.stints):
            return
        stint = self._plan.stints[index]
        new_end = stint.start_lap + laps - 1
        self._plan.stints[index] = PlannedStint(
            compound=stint.compound,
            start_lap=stint.start_lap,
            end_lap=new_end,
            fuel_at_start=stint.fuel_at_start,
            fuel_to_add=stint.fuel_to_add,
            grip_at_end=stint.grip_at_end,
            estimated_time_s=stint.estimated_time_s,
        )
        self.planChanged.emit()

    @safe_slot()
    @Slot(str)
    def addStint(self, compound: str) -> None:  # noqa: N802
        if self._plan is None:
            return
        last_lap = self._plan.stints[-1].end_lap if self._plan.stints else 0
        if compound in self._profiles:
            profile = self._profiles[compound]
            stint_len = min(profile.estimated_life, max(1, self._total_laps - last_lap))
        else:
            stint_len = 10
        self._plan.stints.append(PlannedStint(
            compound=compound,
            start_lap=last_lap + 1,
            end_lap=last_lap + stint_len,
            fuel_at_start=self._fuel_capacity,
            fuel_to_add=self._fuel_capacity,
            grip_at_end=50.0,
            estimated_time_s=0.0,
        ))
        self.planChanged.emit()

    @safe_slot()
    @Slot(int)
    def removeStint(self, index: int) -> None:  # noqa: N802
        if self._plan is None or index < 0 or index >= len(self._plan.stints):
            return
        self._plan.stints.pop(index)
        self.planChanged.emit()

    # -- Coaching loop ---------------------------------------------------------

    def _maybe_update_coaching_plan(self) -> None:
        """Generate a new plan or evaluate an existing one based on lap progress."""
        report = analyze_consistency(self._lap_times_buffer)
        if report is None:
            return

        insights = self._corner_insights_latest or None

        # If we have an active plan, check if evaluation window elapsed
        if (
            self._active_plan is not None
            and self._laps_since_plan >= self._active_plan.evaluation_window
        ):
            post_laps = self._lap_times_buffer[-self._active_plan.evaluation_window:]
            if len(self._pre_plan_lap_times) >= self._active_plan.evaluation_window:
                pre_laps = self._pre_plan_lap_times[-self._active_plan.evaluation_window:]
            else:
                pre_laps = self._pre_plan_lap_times
            if pre_laps:
                result_output = evaluate_plan(self._active_plan, pre_laps, post_laps)
                self._last_plan_result = result_output.value
                plan_output = generate_plan(
                    report, len(self._lap_times_buffer), self._last_plan_result,
                    corner_insights=insights,
                )
            else:
                plan_output = generate_plan(
                    report, len(self._lap_times_buffer), None,
                    corner_insights=insights,
                )
        else:
            # No active plan or still evaluating — generate/refresh
            plan_output = generate_plan(
                report, len(self._lap_times_buffer), self._last_plan_result,
                corner_insights=insights,
            )

        # Update active plan if we got a fresh one
        new_plan = (
            plan_output.value
            if plan_output.value is not None
            and hasattr(plan_output.value, "focus_area")
            else None
        )
        if new_plan is not None and (
            self._active_plan is None
            or new_plan.focus_area != self._active_plan.focus_area
        ):
            self._active_plan = new_plan
            self._pre_plan_lap_times = list(self._lap_times_buffer)
            self._laps_since_plan = 0

            # Emit CoachingPayload whenever the active plan changes
            if (
                self._sync_queue is not None
                and self._session_id
                and self._active_plan is not None
            ):
                if report is not None:
                    coaching_payload = CoachingPayload(
                        session_id=self._session_id,
                        consistency_score=report.consistency_pct,
                        trend=report.trend,
                        focus_area=self._active_plan.focus_area,
                        recommendation=self._active_plan.objective,
                        confidence=self._active_plan.confidence.value,
                    )
                    if not coaching_payload.validate():
                        envelope = SyncEnvelope(
                            payload_type="coaching",
                            payload=coaching_payload.to_dict(),
                        )
                        self._sync_queue.enqueue(envelope)
        else:
            self._laps_since_plan += 1

    # -- Weather ---------------------------------------------------------------

    def set_weather_conditions(self, conditions: list[ConditionWindow]) -> None:
        self._conditions = conditions
        self.weatherChanged.emit()

    # -- Live update -----------------------------------------------------------

    def update_live(self, snap: dict[str, Any]) -> None:
        try:
            self._update_live_impl(snap)
        except Exception:
            log.debug("update_live failed", exc_info=True)

    def _update_live_impl(self, snap: dict[str, Any]) -> None:
        validated = validate_live(snap)
        if validated is None:
            return
        snap = validated.raw  # now guaranteed to be a real dict
        if not snap:
            return
        # Accumulate snapshots for data mode inspection
        self._snapshot_buffer.append(dict(snap))
        if len(self._snapshot_buffer) > self._snapshot_buffer_max:
            self._snapshot_buffer = self._snapshot_buffer[-self._snapshot_buffer_max:]

        # Estimate sample rate from session_time_s deltas
        t = snap.get("session_time_s")
        if t is not None and self._last_snapshot_time is not None:
            try:
                dt = float(t) - self._last_snapshot_time
                if 0 < dt < 1.0:  # plausible sample interval
                    instant_hz = 1.0 / dt
                    # Exponential moving average for stability
                    if self._sample_rate_hz == 0:
                        self._sample_rate_hz = instant_hz
                    else:
                        self._sample_rate_hz = (
                            self._sample_rate_hz * 0.9 + instant_hz * 0.1
                        )
            except (ValueError, TypeError):
                pass
        if t is not None:
            try:
                self._last_snapshot_time = float(t)
            except (ValueError, TypeError):
                pass

        # Auto-detect fuel capacity from telemetry
        if self._fuel_capacity <= 0:
            fuel_cap = snap.get("fuel_capacity")
            if fuel_cap is not None:
                try:
                    cap = float(fuel_cap)
                    if cap > 0:
                        self._fuel_capacity = cap
                        self.planChanged.emit()
                except (ValueError, TypeError):
                    pass

        # Auto-detect track and car from telemetry
        if not self._track:
            track = snap.get("track_name")
            car = snap.get("car_name")
            if track and car:
                self.setTrackCar(str(track), str(car))

        # Car class resolution from LUT. Cheap, runs at most once per
        # (sim, car) pair. Desktop is the authoritative resolver; empty
        # string falls back to GT3 calibration in the overlay.
        sim_id = snap.get("sim")
        if sim_id and self._car and self._sim_id != str(sim_id):
            self._sim_id = str(sim_id)
            self._resolve_car_class(self._sim_id, self._car)

        # -- Fuel tracking for live strategy -----------------------------------
        fuel_level = snap.get("fuel_level")
        if fuel_level is not None:
            self._current_fuel = float(fuel_level)
            # Initialise on first reading so delta tracking works from lap 1
            if self._prev_fuel_level is None:
                self._prev_fuel_level = self._current_fuel

        # Pit-entry detection for auto-capture + plan-vs-actual recording
        is_in_pits = bool(snap.get("is_in_pits", False))
        was_in_pits = self._was_in_pits
        if is_in_pits and not was_in_pits:
            self.on_pit_detected()
            # Record actual pit event for plan-vs-actual review
            if self._race_active and self._prev_consistency_lap > 0:
                self._actual_pit_laps.append(self._prev_consistency_lap)
        if not is_in_pits and was_in_pits and self._race_active:
            # Pit exit — track fuel added (delta from entry to exit)
            if self._prev_fuel_level is not None and self._current_fuel > self._prev_fuel_level:
                self._actual_fuel_added.append(round(self._current_fuel - self._prev_fuel_level, 2))
        self._was_in_pits = is_in_pits

        # Track lap times for consistency analysis
        lap = snap.get("lap_number")
        session_time = snap.get("session_time_s")
        if lap is not None and session_time is not None:
            current_lap = int(lap)
            if hasattr(self, "_prev_consistency_lap") and current_lap != self._prev_consistency_lap:
                if hasattr(self, "_prev_consistency_time") and self._prev_consistency_time is not None:
                    lap_time = float(session_time) - self._prev_consistency_time
                    if 20 < lap_time < 600:
                        self._lap_times_buffer.append(lap_time)

                        # Emit LapPayload for the lap that just completed
                        if self._sync_queue is not None and self._session_id:
                            lap_payload = LapPayload(
                                session_id=self._session_id,
                                lap_number=self._prev_consistency_lap,
                                lap_time_s=lap_time,
                                valid=True,  # detailed validity flag comes later
                                fuel_used_l=0.0,  # populated when fuel delta is tracked
                                sector_times_s=[],
                                consistency_pct=None,
                                std_dev_s=None,
                            )
                            if not lap_payload.validate():
                                envelope = SyncEnvelope(
                                    payload_type="lap",
                                    payload=lap_payload.to_dict(),
                                )
                                self._sync_queue.enqueue(envelope)
                                self._last_synced_lap = self._prev_consistency_lap

                        self._maybe_update_coaching_plan()

                        # -- Live strategy recalculation (v2 redesign) --------
                        # Track per-lap fuel consumption
                        if self._prev_fuel_level is not None and self._current_fuel > 0:
                            delta = self._prev_fuel_level - self._current_fuel
                            if 0 < delta < 20:  # sanity: 0-20L per lap
                                self._fuel_deltas.append(round(delta, 3))
                        self._prev_fuel_level = self._current_fuel

                        # Recalculate strategy if we have a plan and we're racing
                        if (
                            self._plan is not None
                            and self._race_active
                            and self._mode in ("sprint", "endurance")
                            and len(self._fuel_deltas) >= 1
                        ):
                            self._recalculate_live_strategy()

                        self.profilesChanged.emit()
                self._prev_consistency_time = float(session_time)
            elif not hasattr(self, "_prev_consistency_lap"):
                self._prev_consistency_time = float(session_time)
            self._prev_consistency_lap = current_lap

        if self._recorder and self._recorder.is_recording:
            self._recorder.push_snapshot(snap)

            # Auto-update pit time from measured pit stops
            measured = self._recorder.measured_pit_time_s
            if measured is not None and abs(measured - self._pit_time) > 1.0:
                self._pit_time = round(measured, 1)
                self.planChanged.emit()
