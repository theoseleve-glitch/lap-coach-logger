"""StrategyViewModel -- QObject bridge between strategy engine and QML."""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot

from lap_coach_logger.core.practice_readiness import (
    compute_nudges,
    compute_race_statistics,
    compute_readiness,
)
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

    # -- QML properties --------------------------------------------------------

    @Property(str, notify=profilesChanged)
    def trackName(self) -> str:  # noqa: N802
        return self._track

    @Property(str, notify=profilesChanged)
    def carName(self) -> str:  # noqa: N802
        return self._car

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

    @Property(str, notify=planChanged)
    def currentMode(self) -> str:  # noqa: N802
        return self._mode

    @Property(list, notify=planChanged)
    def tabsForMode(self) -> list[dict]:  # noqa: N802
        if self._mode == "sprint":
            return [{"id": "setup", "label": "SETUP"}, {"id": "live", "label": "LIVE"}]
        if self._mode == "endurance":
            return [{"id": "practice", "label": "PRACTICE"}, {"id": "build", "label": "BUILD"}, {"id": "raceplan", "label": "RACE PLAN"}]
        if self._mode == "coaching":
            return [{"id": "consistency", "label": "CONSISTENCY"}, {"id": "pace", "label": "PACE"}, {"id": "readiness", "label": "READINESS"}]
        if self._mode == "data":
            return [{"id": "telemetry", "label": "TELEMETRY"}, {"id": "export", "label": "EXPORT"}]
        return []

    @Property(str, notify=planChanged)
    def activeTab(self) -> str:  # noqa: N802
        if self._mode == "sprint":
            return "live" if self._plan is not None else "setup"
        if self._mode == "data":
            return "telemetry"
        # endurance + coaching: existing logic
        if self._plan is not None:
            return "raceplan"
        if self._profiles:
            return "build"
        return "practice"

    # -- Mode setter (called from bootstrap wiring) ----------------------------

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.planChanged.emit()

    # -- Slots -----------------------------------------------------------------

    @Slot(str, str)
    def setTrackCar(self, track: str, car: str) -> None:  # noqa: N802
        self._track = track
        self._car = car
        self._profiles = self._store.get_profiles(track, car)
        self.profilesChanged.emit()
        self.stintLogChanged.emit()

    @Slot(int)
    def setTotalLaps(self, n: int) -> None:  # noqa: N802
        self._total_laps = max(0, n)
        self.planChanged.emit()

    @Slot(float)
    def setFuelCapacity(self, v: float) -> None:  # noqa: N802
        self._fuel_capacity = max(0, v)
        self.planChanged.emit()

    @Slot(float)
    def setPitTime(self, v: float) -> None:  # noqa: N802
        self._pit_time = max(0, v)
        self.planChanged.emit()

    @Slot(str)
    def setRaceMode(self, mode: str) -> None:  # noqa: N802
        if mode in ("laps", "timed"):
            self._race_mode = mode
            self.planChanged.emit()

    @Slot(float)
    def setRaceDurationHours(self, hours: float) -> None:  # noqa: N802
        self._race_duration_hours = max(0.0, hours)
        self.planChanged.emit()

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
        self.planChanged.emit()
        self.alertsChanged.emit()

    @Slot(str)
    def startRecording(self, compound: str) -> None:  # noqa: N802
        self._recorder = StintRecorder(
            store=self._store, track=self._track, car=self._car,
        )
        self._recorder.start(compound)
        self.recordingChanged.emit()

    @Slot()
    def stopRecording(self) -> None:  # noqa: N802
        if self._recorder and self._recorder.is_recording:
            self._recorder.stop()
            self._profiles = self._store.get_profiles(self._track, self._car)
            self.profilesChanged.emit()
            self.stintLogChanged.emit()
        self.recordingChanged.emit()

    @Slot(str)
    def excludeLoggedStint(self, stint_id: str) -> None:  # noqa: N802
        self._store.exclude_stint(stint_id)
        self._profiles = self._store.get_profiles(self._track, self._car)
        self.profilesChanged.emit()
        self.stintLogChanged.emit()

    @Slot(str)
    def includeLoggedStint(self, stint_id: str) -> None:  # noqa: N802
        self._store.include_stint(stint_id)
        self._profiles = self._store.get_profiles(self._track, self._car)
        self.profilesChanged.emit()
        self.stintLogChanged.emit()

    @Slot()
    def clearStints(self) -> None:  # noqa: N802
        self._store.clear(self._track, self._car)
        self._profiles = {}
        self.profilesChanged.emit()
        self.stintLogChanged.emit()

    # -- Auto-capture lifecycle ------------------------------------------------

    _AUTO_RECORD_SESSIONS = frozenset({
        "practice", "qualifying", "lone qualify", "open qualify",
    })

    def on_session_detected(self, session_type: str, track: str, car: str) -> None:
        """Called when a new session is detected from telemetry."""
        self.setTrackCar(track, car)
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

    def on_session_ended(self) -> None:
        """Called when the session ends."""
        if self._recorder and self._recorder.is_recording:
            self._recorder.stop()
            self._profiles = self._store.get_profiles(self._track, self._car)
            self.profilesChanged.emit()
            self.stintLogChanged.emit()
        self._recorder = None
        self.recordingChanged.emit()

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

    @Slot(int)
    def removeStint(self, index: int) -> None:  # noqa: N802
        if self._plan is None or index < 0 or index >= len(self._plan.stints):
            return
        self._plan.stints.pop(index)
        self.planChanged.emit()

    # -- Weather ---------------------------------------------------------------

    def set_weather_conditions(self, conditions: list[ConditionWindow]) -> None:
        self._conditions = conditions
        self.weatherChanged.emit()

    # -- Live update -----------------------------------------------------------

    def update_live(self, snap: dict[str, Any]) -> None:
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

        # Pit-entry detection for auto-capture
        is_in_pits = bool(snap.get("is_in_pits", False))
        was_in_pits = self._was_in_pits
        if is_in_pits and not was_in_pits:
            self.on_pit_detected()
        self._was_in_pits = is_in_pits

        if self._recorder and self._recorder.is_recording:
            self._recorder.push_snapshot(snap)

            # Auto-update pit time from measured pit stops
            measured = self._recorder.measured_pit_time_s
            if measured is not None and abs(measured - self._pit_time) > 1.0:
                self._pit_time = round(measured, 1)
                self.planChanged.emit()
