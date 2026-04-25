"""OverlayViewModel -- live HUD overlay bridge for QML.

Reads coordinator snapshots and exposes telemetry and context
properties for a floating overlay / HUD panel.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Property, QObject, Signal, Slot

from lap_coach_logger.coaching.corner_insights import (
    CornerInsight,
    format_corner_prompt,
)
from lap_coach_logger.coaching.policy_config import RACE_OVERLAY_POLICY
from lap_coach_logger.coaching.presentation import CoachingMessage
from lap_coach_logger.coaching.surface_policy import (
    SurfaceState,
    compute_surface_state,
)
from lap_coach_logger.core.live_telemetry_processor import LiveTelemetryProcessor
from lap_coach_logger.core.pit_call_state import (
    PitCallState,
    STATE_ON_PLAN,
    advance_pit_call_state,
)
from lap_coach_logger.core.race_strategy import RaceStrategy
from lap_coach_logger.core.race_strategy_service import RaceStrategyService
from lap_coach_logger.utils.overlay_hwnd import apply_overlay_flags, apply_overlay_flags_to_all_overlays, remove_overlay_flags
from lap_coach_logger.utils.qt_safe_slot import safe_slot
from lap_coach_logger.viewmodels.overlay_helpers import (
    ACCENT_COLORS,
    LAYOUT_PRESETS,
    PRESET_LIST,
    WIDGET_CATEGORIES,
    build_sector_states,
    calc_brake_temp_max,
    calc_fuel_state,
    calc_tyre_temp_avg,
    compute_scaled_widget,
    extract_coaching_top_card,
    extract_context,
    extract_telemetry_inputs,
    get_widget_float,
    get_widget_int,
    make_default_widget_settings,
)

from lap_coach_logger.core.mode_descriptor import get_mode

log = logging.getLogger(__name__)


class OverlayViewModel(QObject):
    """Exposes live overlay HUD state as flat, QML-bindable properties."""

    # -- change signals --------------------------------------------------------
    timesChanged = Signal()
    inputsChanged = Signal()
    contextChanged = Signal()
    fuelChanged = Signal()
    deltaChanged = Signal()
    coachingChanged = Signal()
    widgetSettingsChanged = Signal()
    selectedWidgetChanged = Signal()
    overlayLockChanged = Signal()
    settingsSaveRequested = Signal()
    accentChanged = Signal()
    strategyChanged = Signal()
    pitArmedChanged = Signal()
    strategyGuidanceChanged = Signal()
    decisionPromptChanged = Signal()
    cornerPromptChanged = Signal()
    tireChanged = Signal()

    # -- widget category mapping -----------------------------------------------

    _WIDGET_CATEGORIES: dict[str, str] = WIDGET_CATEGORIES

    # -- accent colour palette -------------------------------------------------

    _ACCENT_COLORS: dict[str, str] = ACCENT_COLORS

    # -- layout presets --------------------------------------------------------

    _PRESETS: dict[str, dict[str, dict]] = LAYOUT_PRESETS

    # -- construction ----------------------------------------------------------

    def __init__(self, saved_settings: dict | None = None) -> None:
        super().__init__()

        # Live telemetry processor (lap delta pipeline)
        self._processor = LiveTelemetryProcessor()

        # Telemetry inputs
        self._speed_kph: float = 0.0
        self._throttle_pct: float = 0.0
        self._brake_pct: float = 0.0
        self._steering_deg: float = 0.0
        self._lat_accel_g: float = 0.0
        self._long_accel_g: float = 0.0
        self._lap_progress: float = 0.0
        self._lap_dist_pct: float = 0.0

        # Lap timing
        self._last_time: str = ""
        self._best_time: str = ""
        self._last_delta: str = ""
        self._sector_states: list = []

        # Live delta (processor-driven)
        self._live_delta: float = 0.0
        self._current_lap_time: str = ""

        # Context
        self._lap_number: int = 0
        self._track: str = ""
        self._car: str = ""
        self._car_class: str = ""        # e.g. "GT3" — drives fuel calibration
        self._is_recording: bool = False
        self._elapsed: str = ""
        self._gear: int = 0
        self._rpm: int = 0

        # Additional vehicle state
        self._clutch_pct: float = 0.0
        self._position: int = 0
        self._num_cars: int = 0

        # Temperatures
        self._tyre_temp_avg: float = 0.0
        self._brake_temp_max: float = 0.0
        self._track_temp: float = 0.0
        self._air_temp: float = 0.0

        # Session info
        self._session_type: str = ""
        self._track_length_m: float = 0.0

        # Flag state
        self._current_flag: str = "none"

        # Detection flags
        self._lockup_active: bool = False
        self._wheelspin_active: bool = False
        self._input_smoothness: float = 0.75

        # Corner analysis
        self._corner_rows: list[dict] = []

        # Coaching
        self._coaching_cards: list[dict] = []
        self._coaching_visible: bool = False
        self._coaching_headline: str = ""
        self._coaching_sub: str = ""
        self._coaching_category: str = ""
        self._coaching_severity: str = "positive"
        self._coaching_confidence: int = 0
        self._coaching_sector: str = ""

        # Fuel
        self._fuel_level: float = 0.0
        self._fuel_per_lap: float = 0.0
        self._fuel_laps_left: float = 0.0
        self._fuel_state: str = "SAFE"
        self._prev_fuel_level: float = 0.0
        self._lap_fuel_samples: list[float] = []

        # Race strategy
        self._strategy_vm: object | None = None  # StrategyViewModel reference
        self._strategy_service: RaceStrategyService = RaceStrategyService()
        self._strategy: RaceStrategy | None = None
        self._pit_armed: bool = False  # T141: surface service.armed to QML
        # T142: optional pit-armed audio cue. ``None`` = silent.
        # Bootstrap sets a real player closure when the user has
        # ``Enable voice cues`` on; tests inject a list-append.
        # Fires only on the disarmed → armed transition (not on
        # disarm, not on stable-armed snapshots).
        self._pit_arm_audio_player = None
        # T143: when the user manually arms or disarms via the
        # overlay button, the choice latches and the auto-arm
        # threshold (T140) stops mutating the field. The user
        # has to call clearPitArmedOverride() to release control
        # back to auto.
        self._pit_armed_user_overridden: bool = False
        # T148: PUSH/MANAGE/"" advisory string from
        # RaceStrategyService.compute_guidance, refreshed each
        # per-lap recalc. Stored separately so QML signals only
        # fire on transition (avoids per-lap rebinds).
        self._strategy_guidance: str = ""
        # T151: directive prompt from compute_decision_prompt —
        # one of "" / "PIT" / "SAVE FUEL" / "COOL TIRES" / "PUSH".
        # Same transition-only signalling as strategy_guidance.
        self._decision_prompt: str = ""
        self._strategy_total_laps: int = 0
        self._strategy_fuel_capacity: float = 65.0
        self._strategy_pit_time: float = 25.0
        self._strategy_tire_life: int = 30
        self._strategy_next_pit_lap: int = 0
        self._strategy_fuel_to_add: float = 0.0
        self._strategy_stints_remaining: int = 0
        self._strategy_pit_stops: list = []
        self._strategy_fuel_at_finish: float = 0.0
        self._strategy_prev_lap: int = -1
        self._strategy_weather_alert: str = ""

        # Corner-level technique coaching — tracks the last insights lap
        # we forwarded to the strategy VM so we push exactly once per lap
        # finalisation.
        self._technique_last_pushed_lap: int | None = None
        # T152: concise corner prompt ("losing X at T1 — brake later")
        # for the highest-time-loss insight in the latest lap, refreshed
        # in lockstep with the strategy-VM push above.
        self._corner_prompt: str = ""

        # Coaching surface state — updated per snapshot via the policy
        # engine. Kept as a single dataclass so tests can introspect it
        # and QML bindings refresh exactly once per change.
        self._coaching_surface: SurfaceState = SurfaceState()

        # Pit-call state machine — the deterministic source for the
        # pit_countdown + strategy_status widgets. Advanced once per
        # snapshot from (lapsToPit, is_in_pits, was_in_pits); all widget
        # properties derive from it so they can't contradict each other.
        self._pit_call_state: PitCallState = PitCallState()
        self._was_in_pits_prev: bool = False

        # Tire state
        self._tire_grip_pct: float = 100.0
        self._tire_lap_count: int = 0
        self._tire_laps_remaining: int = 99
        self._tire_condition: str = "good"
        self._tire_temp_lf: float = 0.0
        self._tire_temp_rf: float = 0.0
        self._tire_temp_lr: float = 0.0
        self._tire_temp_rr: float = 0.0

        # Per-widget settings (widget_id -> settings dict)
        self._widget_settings: dict[str, dict] = make_default_widget_settings()
        self._widget_defaults: dict[str, dict] = {
            k: dict(v) for k, v in self._widget_settings.items()
        }

        # Merge persisted settings over defaults (saved values win)
        if saved_settings:
            for wid, saved in saved_settings.items():
                if wid in self._widget_settings and isinstance(saved, dict):
                    self._widget_settings[wid].update(saved)

        self._selected_widget: str = "delta_timing"
        self._overlay_locked: bool = False
        self._overlay_accent: str = "purple"  # default Racing Purple
        self._snap_enabled: bool = True

        # Auto-hide overlays when not on track
        self._auto_hide_enabled: bool = True
        self._should_show_overlays: bool = True
        self._has_been_recording: bool = False

    # -- QML properties --------------------------------------------------------

    @Property(float, notify=inputsChanged)
    def speedKph(self) -> float:  # noqa: N802
        """Current speed in km/h."""
        return self._speed_kph

    @Property(float, notify=inputsChanged)
    def throttlePct(self) -> float:  # noqa: N802
        """Throttle position as a percentage (0-100)."""
        return self._throttle_pct

    @Property(float, notify=inputsChanged)
    def brakePct(self) -> float:  # noqa: N802
        """Brake position as a percentage (0-100)."""
        return self._brake_pct

    @Property(str, notify=timesChanged)
    def lastTime(self) -> str:  # noqa: N802
        """Formatted last lap time."""
        return self._last_time

    @Property(str, notify=timesChanged)
    def bestTime(self) -> str:  # noqa: N802
        """Formatted best lap time."""
        return self._best_time

    @Property(str, notify=timesChanged)
    def lastDelta(self) -> str:  # noqa: N802
        """Delta vs best as ``+X.XXX`` / ``-X.XXX``."""
        return self._last_delta

    @Property("QVariant", notify=timesChanged)
    def sectorStates(self) -> list:  # noqa: N802
        """Sector state list for sector indicator display."""
        return self._sector_states

    @Property(int, notify=contextChanged)
    def lapNumber(self) -> int:  # noqa: N802
        """Current lap number."""
        return self._lap_number

    @Property(str, notify=contextChanged)
    def track(self) -> str:
        """Track name (falls back to sim name)."""
        return self._track

    @Property(bool, notify=contextChanged)
    def isRecording(self) -> bool:  # noqa: N802
        """Whether the session is actively recording."""
        return self._is_recording

    @Property(str, notify=contextChanged)
    def elapsed(self) -> str:
        """Formatted elapsed session time."""
        return self._elapsed

    @Property(float, notify=inputsChanged)
    def steeringDeg(self) -> float:  # noqa: N802
        return self._steering_deg

    @Property(float, notify=inputsChanged)
    def latAccelG(self) -> float:  # noqa: N802
        return self._lat_accel_g

    @Property(float, notify=inputsChanged)
    def longAccelG(self) -> float:  # noqa: N802
        return self._long_accel_g

    @Property(int, notify=contextChanged)
    def gear(self) -> int:
        return self._gear

    @Property(int, notify=contextChanged)
    def rpm(self) -> int:
        return self._rpm

    @Property(str, notify=contextChanged)
    def car(self) -> str:
        return self._car

    @Property(float, notify=inputsChanged)
    def clutchPct(self) -> float:  # noqa: N802
        """Clutch position as a percentage (0-100)."""
        return self._clutch_pct

    @Property(int, notify=contextChanged)
    def position(self) -> int:
        """Race position (1-based)."""
        return self._position

    @Property(int, notify=contextChanged)
    def numCars(self) -> int:  # noqa: N802
        """Total cars in session."""
        return self._num_cars

    @Property(float, notify=inputsChanged)
    def tyreTempAvg(self) -> float:  # noqa: N802
        """Average tyre temperature across all four corners."""
        return self._tyre_temp_avg

    @Property(float, notify=inputsChanged)
    def brakeTempMax(self) -> float:  # noqa: N802
        """Maximum brake temperature across all four corners."""
        return self._brake_temp_max

    @Property(float, notify=contextChanged)
    def trackTemp(self) -> float:  # noqa: N802
        """Track surface temperature in degrees C."""
        return self._track_temp

    @Property(float, notify=contextChanged)
    def airTemp(self) -> float:  # noqa: N802
        """Ambient air temperature in degrees C."""
        return self._air_temp

    @Property(str, notify=contextChanged)
    def sessionType(self) -> str:  # noqa: N802
        """Session type (Practice, Qualifying, Race, etc.)."""
        return self._session_type

    @Property(float, notify=contextChanged)
    def trackLengthM(self) -> float:  # noqa: N802
        """Track length in metres."""
        return self._track_length_m

    @Property(str, notify=contextChanged)
    def currentFlag(self) -> str:  # noqa: N802
        """Current flag state (none, green, yellow, red, blue, white, checkered)."""
        return self._current_flag

    @Property(float, notify=inputsChanged)
    def lapProgress(self) -> float:  # noqa: N802
        return self._lap_progress

    @Property(float, notify=inputsChanged)
    def lapDistPct(self) -> float:  # noqa: N802
        return self._lap_dist_pct

    @Property(bool, notify=inputsChanged)
    def lockupActive(self) -> bool:  # noqa: N802
        """True while a wheel-lockup condition is detected."""
        return self._lockup_active

    @Property(bool, notify=inputsChanged)
    def wheelspinActive(self) -> bool:  # noqa: N802
        """True while a wheelspin condition is detected."""
        return self._wheelspin_active

    @Property(float, notify=inputsChanged)
    def inputSmoothness(self) -> float:  # noqa: N802
        return self._input_smoothness

    @Property(bool, notify=coachingChanged)
    def coachingVisible(self) -> bool:  # noqa: N802
        return self._coaching_visible

    @Property(str, notify=coachingChanged)
    def coachingHeadline(self) -> str:  # noqa: N802
        return self._coaching_headline

    @Property(str, notify=coachingChanged)
    def coachingSub(self) -> str:  # noqa: N802
        return self._coaching_sub

    @Property(str, notify=coachingChanged)
    def coachingCategory(self) -> str:  # noqa: N802
        return self._coaching_category

    @Property(str, notify=coachingChanged)
    def coachingSeverity(self) -> str:  # noqa: N802
        return self._coaching_severity

    @Property(int, notify=coachingChanged)
    def coachingConfidence(self) -> int:  # noqa: N802
        return self._coaching_confidence

    @Property(str, notify=coachingChanged)
    def coachingSector(self) -> str:  # noqa: N802
        return self._coaching_sector

    # -- Technique coaching (corner-level self-comparison) --------------------
    # These properties proxy the strategy VM's coaching plan so the overlay
    # can render a compact technique card without duplicating state.

    def _strategy_attr(self, name: str, default: str = "") -> str:
        vm = self._strategy_vm
        return str(getattr(vm, name, default)) if vm is not None else default

    # -- Coaching surface state (policy-governed) ----------------------------
    # Thin QML accessors over self._coaching_surface; all upstream gating
    # (visibility, cooldown, hysteresis, formatting) lives in surface_policy.

    @Property(bool, notify=coachingChanged)
    def coachingSurfaceVisible(self) -> bool:  # noqa: N802
        return self._coaching_surface.visible

    @Property(str, notify=coachingChanged)
    def coachingSurfaceHeadline(self) -> str:  # noqa: N802
        return self._coaching_surface.message.headline

    @Property(str, notify=coachingChanged)
    def coachingSurfaceSub(self) -> str:  # noqa: N802
        return self._coaching_surface.message.subline

    @Property(str, notify=coachingChanged)
    def coachingSurfaceSeverity(self) -> str:  # noqa: N802
        return self._coaching_surface.message.severity

    @Property(str, notify=coachingChanged)
    def coachingSurfaceCategory(self) -> str:  # noqa: N802
        return self._coaching_surface.message.category

    @Property(str, notify=coachingChanged)
    def coachingSurfaceFocus(self) -> str:  # noqa: N802
        return self._coaching_surface.message.focus_id

    @Property(str, notify=coachingChanged)
    def coachingSurfaceFreshness(self) -> str:  # noqa: N802
        """Freshness state: 'live' / 'carryover' / 'stale' (replaces
        the legacy time_loss sentinel so QML can distinguish an active
        coaching tip from a carryover display)."""
        return self._coaching_surface.freshness

    @Property(str, notify=coachingChanged)
    def techniqueCornerFocus(self) -> str:  # noqa: N802
        """Corner the coaching plan is targeting (empty for sector focus)."""
        return self._strategy_attr("cornerFocus")

    @Property(str, notify=coachingChanged)
    def techniqueInsight(self) -> str:  # noqa: N802
        """Concise data-driven coaching statement from the latest plan."""
        return self._strategy_attr("techniqueInsight")

    @Property(str, notify=coachingChanged)
    def techniqueAction(self) -> str:  # noqa: N802
        """One-line action hint from the corner insight."""
        return self._strategy_attr("techniqueAction")

    @Property(str, notify=coachingChanged)
    def techniqueConfidence(self) -> str:  # noqa: N802
        """Confidence tier of the technique insight: high/medium/low."""
        return self._strategy_attr("techniqueConfidence", "low")

    @Property("QVariant", notify=deltaChanged)
    def cornerRows(self) -> list:  # noqa: N802
        return self._corner_rows

    @Property(float, notify=deltaChanged)
    def liveDelta(self) -> float:  # noqa: N802
        """Real-time delta vs best lap in seconds (from processor)."""
        return self._live_delta

    @Property(str, notify=deltaChanged)
    def currentLapTime(self) -> str:  # noqa: N802
        """Formatted elapsed time for the current lap (from processor)."""
        return self._current_lap_time

    @Property(float, notify=fuelChanged)
    def fuelLevel(self) -> float:  # noqa: N802
        return self._fuel_level

    @Property(float, notify=fuelChanged)
    def fuelPerLap(self) -> float:  # noqa: N802
        return self._fuel_per_lap

    @Property(float, notify=fuelChanged)
    def fuelLapsLeft(self) -> float:  # noqa: N802
        return self._fuel_laps_left

    @Property(str, notify=fuelChanged)
    def fuelState(self) -> str:  # noqa: N802
        return self._fuel_state

    # -- Strategy properties ---------------------------------------------------

    @Property(int, notify=strategyChanged)
    def strategyNextPitLap(self) -> int:  # noqa: N802
        """Lap number for the next planned pit stop."""
        return self._strategy_next_pit_lap

    @Property(float, notify=strategyChanged)
    def strategyFuelToAdd(self) -> float:  # noqa: N802
        """Liters of fuel to add at the next pit stop."""
        return self._strategy_fuel_to_add

    @Property(int, notify=strategyChanged)
    def strategyStintsRemaining(self) -> int:  # noqa: N802
        """Number of pit stops still remaining."""
        return self._strategy_stints_remaining

    @Property("QVariant", notify=strategyChanged)
    def strategyPitStops(self) -> list:  # noqa: N802
        """List of pit stop dicts for QML display."""
        return self._strategy_pit_stops

    @Property(float, notify=strategyChanged)
    def strategyFuelAtFinish(self) -> float:  # noqa: N802
        """Estimated fuel remaining at the chequered flag."""
        return self._strategy_fuel_at_finish

    @Property(int, notify=strategyChanged)
    def strategyTotalLaps(self) -> int:  # noqa: N802
        """Total laps in the current strategy."""
        return self._strategy_total_laps

    @Property(str, notify=strategyChanged)
    def strategyWeatherAlert(self) -> str:  # noqa: N802
        """One-line weather alert text from the strategy plan."""
        return self._strategy_weather_alert

    @Property(bool, notify=pitArmedChanged)
    def pitArmed(self) -> bool:  # noqa: N802
        """T141: pit-armed state from :class:`RaceStrategyService`.

        QML's strategy widget binds an ``ARMED`` indicator and
        colour change against this property; the VM updates it
        from the service after each live recalc."""
        return self._pit_armed

    @Property(str, notify=strategyGuidanceChanged)
    def strategyGuidance(self) -> str:  # noqa: N802
        """T148: ``"PUSH"`` / ``"MANAGE"`` / ``""`` advisory.

        QML strategy widget binds the visible label against this
        property; the VM refreshes it from
        :meth:`RaceStrategyService.compute_guidance` after each
        live recalc. Empty string hides the label."""
        return self._strategy_guidance

    @Property(str, notify=decisionPromptChanged)
    def decisionPrompt(self) -> str:  # noqa: N802
        """T151: directive driver prompt — one of ``""`` /
        ``"PIT"`` / ``"SAVE FUEL"`` / ``"COOL TIRES"`` / ``"PUSH"``.

        Sharper than :attr:`strategyGuidance` (which is just
        PUSH/MANAGE pace mode); the prompt names the specific
        action. Refreshed from
        :meth:`RaceStrategyService.compute_decision_prompt`
        after each live recalc."""
        return self._decision_prompt

    @Property(str, notify=cornerPromptChanged)
    def cornerPrompt(self) -> str:  # noqa: N802
        """T152: concise corner-specific prompt for the worst
        corner of the most recent lap — e.g. ``"losing 0.3s at
        T1 — brake earlier"``. Empty string when no significant
        loss to surface. Refreshed in lockstep with the
        per-lap insight push to :attr:`_strategy_vm`."""
        return self._corner_prompt

    # -- Redesign v2: derived widget state -------------------------------------

    @Property(int, notify=strategyChanged)
    def lapsToPit(self) -> int:  # noqa: N802
        """Laps to next planned pit. -1 if unknown."""
        vm = self._strategy_vm
        return int(vm.lapsToPit) if vm is not None else -1

    @Property(bool, notify=strategyChanged)
    def pitNow(self) -> bool:  # noqa: N802
        """True when driver should pit THIS lap."""
        vm = self._strategy_vm
        return bool(vm.pitNow) if vm is not None else False

    @Property(float, notify=strategyChanged)
    def pitFuelLoad(self) -> float:  # noqa: N802
        """Fuel to add at next stop (L)."""
        vm = self._strategy_vm
        return float(vm.pitFuelLoad) if vm is not None else 0.0

    @Property(float, notify=strategyChanged)
    def fuelMargin(self) -> float:  # noqa: N802
        """Fuel margin in liters (current - needed).

        Honors ``_mock_fuel_margin_l`` when set by the smoke harness
        (``injectSmokeState``). Production always reads from strategy VM.
        """
        mock = getattr(self, "_mock_fuel_margin_l", None)
        if mock is not None:
            return float(mock)
        vm = self._strategy_vm
        return float(vm.fuelMargin) if vm is not None else 0.0

    def _current_fuel_state(self) -> str:
        """Class-calibrated fuel state shared by the pit + status helpers."""
        from lap_coach_logger.viewmodels.overlay_derived import compute_fuel_state
        return compute_fuel_state(self.fuelMargin, self._car_class)

    def _pit_countdown_display(self):
        """Pit countdown display derived from the pit-call state machine."""
        from lap_coach_logger.viewmodels.overlay_derived import build_pit_countdown_from_state
        return build_pit_countdown_from_state(
            state=self._pit_call_state,
            pit_fuel_load=self.pitFuelLoad,
            fuel_state=self._current_fuel_state(),
        )

    @Property(str, notify=strategyChanged)
    def pitCountdownHeadline(self) -> str:  # noqa: N802
        """Compact headline for pit_countdown widget ("PIT IN 3" / "BOX BOX BOX" / "")."""
        return self._pit_countdown_display().headline

    @Property(str, notify=strategyChanged)
    def pitCountdownSub(self) -> str:  # noqa: N802
        """Sub-text for pit_countdown widget ("38L fuel" / "")."""
        return self._pit_countdown_display().sub

    @Property(str, notify=strategyChanged)
    def pitCountdownSeverity(self) -> str:  # noqa: N802
        """Severity for pit_countdown widget ("ok" / "advisory" / "critical")."""
        return self._pit_countdown_display().severity

    @Property(bool, notify=strategyChanged)
    def pitCountdownVisible(self) -> bool:  # noqa: N802
        """Whether pit_countdown should render (``on_plan`` is the only hidden state)."""
        return self._pit_countdown_display().visible

    @Property(str, notify=strategyChanged)
    def pitCallState(self) -> str:  # noqa: N802
        """Current pit-call state label (for diagnostics / QML styling)."""
        return self._pit_call_state.state

    def _strategy_status_obj(self):
        """Strategy status derived from the same PitCallState that drives
        the countdown widget, so the two can't disagree on severity."""
        from lap_coach_logger.viewmodels.overlay_derived import build_strategy_status_from_state
        return build_strategy_status_from_state(
            position=self._position if self._position > 0 else None,
            current_lap=self._lap_number,
            total_laps=self._strategy_total_laps,
            fuel_state=self._current_fuel_state(),
            grip_pct=self._tire_grip_pct if self._tire_grip_pct > 0 else None,
            pit_state=self._pit_call_state,
        )

    @Property(str, notify=strategyChanged)
    def strategyStatusLine(self) -> str:  # noqa: N802
        """Compact one-line strategy banner ("P5 · L9/20 · Fuel SAFE · Grip 82%")."""
        return self._strategy_status_obj().line

    @Property(str, notify=strategyChanged)
    def strategyStatusSeverity(self) -> str:  # noqa: N802
        """Severity for strategy_status widget."""
        return self._strategy_status_obj().severity

    def _push_manage_state_obj(self):
        """Shared compute for state/reason/confidence/hint properties.

        Prefers live strategy stint data from the strategy VM; falls
        back to legacy tire counters only when the plan isn't active.
        """
        from lap_coach_logger.viewmodels.overlay_derived import (
            compute_fuel_state,
            compute_push_manage,
        )

        # Live stint data (preferred): from strategy VM's live recalc
        live_stint_lap: int | None = None
        live_stint_total: int | None = None
        has_live = False
        vm = self._strategy_vm
        if vm is not None:
            try:
                lap = int(vm.currentStintLap)
                total = int(vm.currentStintTotalLaps)
                if lap > 0 and total > 0:
                    live_stint_lap = lap
                    live_stint_total = total
                    has_live = True
            except (AttributeError, TypeError, ValueError):
                pass

        # Fallback: legacy tire counter (only if no live data)
        if not has_live:
            if self._tire_lap_count > 0:
                live_stint_lap = self._tire_lap_count
            if self._strategy_tire_life > 0:
                live_stint_total = self._strategy_tire_life

        return compute_push_manage(
            fuel_margin_l=self.fuelMargin,
            fuel_state=compute_fuel_state(self.fuelMargin, self._car_class),
            grip_pct=self._tire_grip_pct if self._tire_grip_pct > 0 else None,
            stint_lap=live_stint_lap,
            stint_total_laps=live_stint_total,
            has_live_stint_data=has_live,
        )

    @Property(str, notify=strategyChanged)
    def pushManageState(self) -> str:  # noqa: N802
        """PUSH / MANAGE / SAVE / HOLD (endurance decision)."""
        return self._push_manage_state_obj().state

    @Property(str, notify=strategyChanged)
    def pushManageReason(self) -> str:  # noqa: N802
        """Short reason explaining the push/manage decision."""
        return self._push_manage_state_obj().reason

    @Property(str, notify=strategyChanged)
    def pushManageConfidence(self) -> str:  # noqa: N802
        """Confidence in the decision: high / medium / low."""
        return self._push_manage_state_obj().confidence

    @Property(str, notify=strategyChanged)
    def pushManageHint(self) -> str:  # noqa: N802
        """One-line driver instruction (widget sub-text)."""
        return self._push_manage_state_obj().hint

    @Property("QVariant", notify=timesChanged)
    def sectorDeltas(self) -> list:  # noqa: N802
        """Per-sector delta list [s1, s2, s3] in seconds vs best lap.

        Each entry may be None (unavailable) — QML widget renders "—"
        for None cells. Always length-3 when populated; empty when no
        processor output has been seen yet.
        """
        deltas = getattr(self, "_sector_deltas", None)
        if not deltas:
            return []
        # QVariant → JS: None passes through as undefined, which QML's
        # isFinite() check rejects correctly.
        return list(deltas)

    # -- Gap timing (iRacing primary source; others degraded) ------------------

    @Property(float, notify=contextChanged)
    def gapAhead(self) -> float:  # noqa: N802
        """Time gap to car ahead in seconds. NaN when adapter doesn't provide it."""
        return float(getattr(self, "_gap_ahead_s", float("nan")))

    @Property(float, notify=contextChanged)
    def gapBehind(self) -> float:  # noqa: N802
        """Time gap to car behind in seconds. NaN when adapter doesn't provide it."""
        return float(getattr(self, "_gap_behind_s", float("nan")))

    @Property(int, notify=contextChanged)
    def positionAhead(self) -> int:  # noqa: N802
        """Position number of the car ahead. 0 when unavailable."""
        return int(getattr(self, "_position_ahead", 0))

    @Property(int, notify=contextChanged)
    def positionBehind(self) -> int:  # noqa: N802
        """Position number of the car behind. 0 when unavailable."""
        return int(getattr(self, "_position_behind", 0))

    # -- Strategy VM wiring ----------------------------------------------------

    def set_strategy_vm(self, vm: object) -> None:
        """Store a reference to the StrategyViewModel and connect its signals."""
        self._strategy_vm = vm
        # Reset the pit-state machine so stale state from a previous
        # session (was_in_pits=True at session exit, or a latched
        # stint_high_water) doesn't produce spurious STOP_COMPLETED
        # latches or suppress a legitimate early pit call in the new
        # session.
        self.reset_pit_state()
        vm.planChanged.connect(self._sync_strategy_from_vm)
        vm.alertsChanged.connect(self._sync_strategy_from_vm)
        # Route the strategy VM's profile/plan updates into our coaching
        # signal so the technique properties refresh on lap boundaries.
        try:
            vm.profilesChanged.connect(self.coachingChanged.emit)
        except Exception:
            # profilesChanged may not exist in very old mocks; ignore.
            pass

    def reset_pit_state(self) -> None:
        """Clear the pit-call state machine back to on_plan.

        Called when the strategy VM is (re-)wired, and from the
        ``clear`` smoke scenario. Emits ``strategyChanged`` so the
        countdown + status widgets refresh immediately.
        """
        if self._pit_call_state.state != STATE_ON_PLAN or self._was_in_pits_prev:
            self._pit_call_state = PitCallState()
            self._was_in_pits_prev = False
            self.strategyChanged.emit()

    def _sync_strategy_from_vm(self) -> None:
        """Read strategy VM state and update overlay properties."""
        vm = self._strategy_vm
        if vm is None:
            return

        # Pull car_class for fuel calibration (resolved by desktop LUT)
        try:
            cls = getattr(vm, "carClass", "") or ""
            if cls and cls != self._car_class:
                self._car_class = str(cls)
        except Exception:
            pass

        plan = vm.racePlan
        if plan:
            # Update total laps from strategy VM
            self._strategy_total_laps = vm.totalLaps

            # Find upcoming stints (fuel_to_add > 0 means a pit stop before it)
            upcoming_stops = [s for s in plan if s.get("start_lap", 0) > self._lap_number and s.get("fuel_to_add", 0) > 0]
            if upcoming_stops:
                first = upcoming_stops[0]
                self._strategy_next_pit_lap = first.get("start_lap", 0)
                self._strategy_fuel_to_add = first.get("fuel_to_add", 0.0)
                self._strategy_stints_remaining = len(upcoming_stops)
            else:
                self._strategy_next_pit_lap = 0
                self._strategy_fuel_to_add = 0.0
                self._strategy_stints_remaining = 0

            self._strategy_pit_stops = [
                {"lap": s.get("start_lap", 0), "fuel": s.get("fuel_to_add", 0.0), "compound": s.get("compound", "")}
                for s in plan
                if s.get("fuel_to_add", 0) > 0
            ]

            # Fuel at finish from last stint
            if plan:
                last = plan[-1]
                laps_in_stint = last.get("end_lap", 0) - last.get("start_lap", 0) + 1
                self._strategy_fuel_at_finish = round(vm.planFuelAtFinish, 1)

        # Weather alert from first weather-category alert
        alerts = vm.alerts
        weather_alert = ""
        for a in alerts:
            if a.get("category") == "weather":
                weather_alert = a.get("message", "")
                break
        self._strategy_weather_alert = weather_alert

        self.strategyChanged.emit()

    # -- Tire properties -------------------------------------------------------

    @Property(float, notify=tireChanged)
    def tireGripPct(self) -> float:  # noqa: N802
        return self._tire_grip_pct

    @Property(int, notify=tireChanged)
    def tireLapCount(self) -> int:  # noqa: N802
        return self._tire_lap_count

    @Property(int, notify=tireChanged)
    def tireLapsRemaining(self) -> int:  # noqa: N802
        return self._tire_laps_remaining

    @Property(str, notify=tireChanged)
    def tireCondition(self) -> str:  # noqa: N802
        return self._tire_condition

    @Property(float, notify=tireChanged)
    def tireTempLF(self) -> float:  # noqa: N802
        return self._tire_temp_lf

    @Property(float, notify=tireChanged)
    def tireTempRF(self) -> float:  # noqa: N802
        return self._tire_temp_rf

    @Property(float, notify=tireChanged)
    def tireTempLR(self) -> float:  # noqa: N802
        return self._tire_temp_lr

    @Property(float, notify=tireChanged)
    def tireTempRR(self) -> float:  # noqa: N802
        return self._tire_temp_rr

    @safe_slot()
    @Slot(int, float, float, int)
    def calculatePreRaceStrategy(self, total_laps: int, fuel_capacity: float, pit_time: float, tire_life: int) -> None:  # noqa: N802
        """Calculate and store pre-race strategy."""
        self._strategy_total_laps = total_laps
        self._strategy_fuel_capacity = fuel_capacity
        self._strategy_pit_time = pit_time
        self._strategy_tire_life = tire_life

        self._strategy = self._strategy_service.compute_pre_race(
            total_laps=total_laps,
            fuel_capacity=fuel_capacity,
            pit_time_s=pit_time,
            tire_life_laps=tire_life,
            fuel_per_lap=self._fuel_per_lap,
        )
        self._apply_strategy(self._strategy)

    @safe_slot()
    @Slot()
    def recalculateLiveStrategy(self) -> None:  # noqa: N802
        """Recalculate strategy from current telemetry."""
        new_strategy = self._strategy_service.recalculate_from_telemetry(
            current_lap=self._lap_number,
            current_fuel=self._fuel_level,
            fuel_per_lap=self._fuel_per_lap,
        )
        if new_strategy is None:
            return
        self._strategy = new_strategy
        self._apply_strategy(new_strategy)
        self._refresh_pit_armed()
        self._refresh_strategy_guidance()
        self._refresh_decision_prompt()

    def _refresh_strategy_guidance(self) -> None:
        """T148: re-evaluate the PUSH/MANAGE label from the
        service and emit :attr:`strategyGuidanceChanged` only on
        transition. Idempotent: identical inputs → identical
        guidance → no signal, so QML doesn't rebind on every
        per-lap recalc when nothing has changed."""
        new_guidance = self._strategy_service.compute_guidance(
            current_lap=self._lap_number,
            current_fuel=self._fuel_level,
        )
        if new_guidance == self._strategy_guidance:
            return
        self._strategy_guidance = new_guidance
        self.strategyGuidanceChanged.emit()

    def _refresh_decision_prompt(self) -> None:
        """T151: re-evaluate the directive prompt from the
        service. Reads ``service.armed`` so MUST run *after*
        :meth:`_refresh_pit_armed` — the order in
        :meth:`recalculateLiveStrategy` enforces this. Same
        transition-only emit pattern as
        :meth:`_refresh_strategy_guidance`."""
        new_prompt = self._strategy_service.compute_decision_prompt(
            current_lap=self._lap_number,
            current_fuel=self._fuel_level,
        )
        if new_prompt == self._decision_prompt:
            return
        self._decision_prompt = new_prompt
        self.decisionPromptChanged.emit()

    @safe_slot()
    @Slot()
    def acknowledgeCornerPrompt(self) -> None:  # noqa: N802
        """T153: minimal-click acknowledgment for the corner
        prompt. Wired from a QML ``Shortcut`` so any keyboard
        / wheel-button mapping can fire it.

        Clears :attr:`cornerPrompt` to ``""`` and emits
        :attr:`cornerPromptChanged` (transition-only — calling
        on an already-empty prompt is a safe no-op so the
        wheel-button hold doesn't churn QML).

        Per-lap not per-session: the next per-lap insight
        push (:meth:`_refresh_corner_prompt`) is free to
        repopulate the prompt with a fresh corner."""
        if self._corner_prompt == "":
            return
        self._corner_prompt = ""
        self.cornerPromptChanged.emit()

    def _refresh_corner_prompt(self, insights: list[CornerInsight]) -> None:
        """T152: pick the highest-time-loss insight from the
        latest lap and surface it as a one-line directive.

        Empty input list (or every entry below the significance
        threshold) clears the prompt. Same transition-only
        emit pattern as :meth:`_refresh_decision_prompt` so
        QML doesn't rebind on stable laps."""
        new_prompt = ""
        if insights:
            ranked = sorted(
                (i for i in insights if i.time_loss_s is not None),
                key=lambda i: abs(i.time_loss_s or 0.0),
                reverse=True,
            )
            for insight in ranked:
                formatted = format_corner_prompt(insight)
                if formatted is not None:
                    new_prompt = formatted
                    break
        if new_prompt == self._corner_prompt:
            return
        self._corner_prompt = new_prompt
        self.cornerPromptChanged.emit()

    def _refresh_pit_armed(self) -> None:
        """T141: ask the service to re-evaluate auto-arming and
        mirror the result onto :attr:`pitArmed`. Emits
        :attr:`pitArmedChanged` only on transition so QML doesn't
        rebind unnecessarily.

        T142: on the disarmed → armed transition, fire the
        configured audio cue if any. Player exceptions are
        swallowed so a misbehaving audio backend can't break
        the per-lap recalc.

        T143: skip the auto update when the user has overridden
        the field manually — their intent outranks the
        threshold until they explicitly release control."""
        if self._pit_armed_user_overridden:
            return
        new_armed = self._strategy_service.update_armed_state(
            current_lap=self._lap_number,
            current_fuel=self._fuel_level,
        )
        self._set_pit_armed(new_armed)

    def _set_pit_armed(self, new_armed: bool) -> None:
        """Apply a new pit-armed value. Centralises the
        transition logic shared between auto-recalc and the
        T143 manual slots: emit the change signal only on a
        real value change, fire the audio cue only on a
        disarmed → armed transition."""
        if new_armed == self._pit_armed:
            return
        transitioned_to_armed = new_armed and not self._pit_armed
        self._pit_armed = new_armed
        self.pitArmedChanged.emit()
        if transitioned_to_armed and self._pit_arm_audio_player is not None:
            try:
                self._pit_arm_audio_player()
            except Exception:  # noqa: BLE001 — audio is opt-in
                pass

    @safe_slot()
    @Slot()
    def armPit(self) -> None:  # noqa: N802
        """T143: user manually arms the pit. Latches the
        override so subsequent auto-recalcs respect the user's
        choice."""
        self._pit_armed_user_overridden = True
        self._set_pit_armed(True)

    @safe_slot()
    @Slot()
    def disarmPit(self) -> None:  # noqa: N802
        """T143: user manually disarms the pit. Latches the
        override even when the value is already False — the
        user's "stay out" intent must survive the next critical
        recalc."""
        self._pit_armed_user_overridden = True
        self._set_pit_armed(False)

    @safe_slot()
    @Slot()
    def clearPitArmedOverride(self) -> None:  # noqa: N802
        """T143: release control back to auto-arming. The next
        recalc will re-evaluate from telemetry as usual."""
        self._pit_armed_user_overridden = False

    def _apply_strategy(self, strat: RaceStrategy) -> None:
        """Push strategy results into QML-bindable properties."""
        stops = strat.pit_stops
        # Find the next upcoming pit stop (first with lap > current)
        upcoming = [s for s in stops if s.lap > self._lap_number]
        if upcoming:
            self._strategy_next_pit_lap = upcoming[0].lap
            self._strategy_fuel_to_add = round(upcoming[0].fuel_to_add, 1)
            self._strategy_stints_remaining = len(upcoming)
        else:
            self._strategy_next_pit_lap = 0
            self._strategy_fuel_to_add = 0.0
            self._strategy_stints_remaining = 0

        self._strategy_pit_stops = [
            {"lap": s.lap, "fuel": round(s.fuel_to_add, 1), "compound": s.tire_compound}
            for s in stops
        ]
        self._strategy_fuel_at_finish = round(strat.fuel_at_finish, 1)
        self.strategyChanged.emit()

    # -- Widget settings properties --------------------------------------------

    @Property("QVariant", notify=widgetSettingsChanged)
    def widgetSettings(self) -> dict:  # noqa: N802
        """Full dict of widget_id -> settings for QML binding."""
        return self._widget_settings

    @Property(bool, notify=overlayLockChanged)
    def overlayLocked(self) -> bool:  # noqa: N802
        """Whether overlay widgets are locked (non-draggable)."""
        return self._overlay_locked

    # -- Accent colour properties ----------------------------------------------

    @Property(str, notify=accentChanged)
    def overlayAccent(self) -> str:  # noqa: N802
        """Active accent colour key (e.g. 'purple', 'orange')."""
        return self._overlay_accent

    @safe_slot()
    @Slot(str)
    def setOverlayAccent(self, accent: str) -> None:  # noqa: N802
        """Switch the overlay accent colour."""
        if accent in self._ACCENT_COLORS and accent != self._overlay_accent:
            self._overlay_accent = accent
            self.accentChanged.emit()
            self.settingsSaveRequested.emit()

    @safe_slot()
    @Slot(result=str)
    def getAccentHex(self) -> str:  # noqa: N802
        """Return the hex value for the current accent colour."""
        return self._ACCENT_COLORS.get(self._overlay_accent, "#8B5CF6")

    @safe_slot()
    @Slot(result="QVariant")
    def getAccentOptions(self) -> list:  # noqa: N802
        """Return the full palette as a list of {id, hex} dicts for QML."""
        return [{"id": k, "hex": v} for k, v in self._ACCENT_COLORS.items()]

    @safe_slot()
    @Slot()
    def toggleOverlayLock(self) -> None:  # noqa: N802
        """Toggle the overlay lock state."""
        self._overlay_locked = not self._overlay_locked
        self.overlayLockChanged.emit()

    @Property(bool, notify=overlayLockChanged)
    def snapEnabled(self) -> bool:  # noqa: N802
        """Whether overlay widgets snap to screen edges when dragged."""
        return self._snap_enabled

    @safe_slot()
    @Slot()
    def toggleSnap(self) -> None:  # noqa: N802
        """Toggle the snap-to-edge behavior."""
        self._snap_enabled = not self._snap_enabled
        self.overlayLockChanged.emit()

    @Property(bool, notify=contextChanged)
    def shouldShowOverlays(self) -> bool:  # noqa: N802
        """Whether overlays should be visible (respects auto-hide logic)."""
        return self._should_show_overlays

    @Property(bool, notify=contextChanged)
    def autoHideEnabled(self) -> bool:  # noqa: N802
        """Whether auto-hide is active (hides overlays when not recording)."""
        return self._auto_hide_enabled

    @safe_slot()
    @Slot()
    def toggleAutoHide(self) -> None:  # noqa: N802
        """Toggle the auto-hide behavior for overlays."""
        self._auto_hide_enabled = not self._auto_hide_enabled
        self.contextChanged.emit()

    @safe_slot()
    @Slot(float)
    def adjustAllOpacity(self, delta: float) -> None:  # noqa: N802
        """Increase or decrease opacity for every widget by *delta*."""
        for wid in self._widget_settings:
            current = self._widget_settings[wid].get("opacity", 0.92)
            new_val = max(0.3, min(1.0, current + delta))
            self._widget_settings[wid]["opacity"] = round(new_val, 2)
        self.widgetSettingsChanged.emit()
        self.settingsSaveRequested.emit()

    @Property(str, notify=selectedWidgetChanged)
    def selectedWidget(self) -> str:  # noqa: N802
        """Currently selected widget id in the overlay manager."""
        return self._selected_widget

    @safe_slot()
    @Slot(str)
    def selectWidget(self, widget_id: str) -> None:  # noqa: N802
        """Select a widget in the overlay manager UI."""
        if widget_id != self._selected_widget:
            self._selected_widget = widget_id
            self.selectedWidgetChanged.emit()

    @safe_slot()
    @Slot(str, str, "QVariant")
    def setWidgetSetting(self, widget_id: str, key: str, value: object) -> None:  # noqa: N802
        """Update a single setting for a widget and notify QML."""
        if self._overlay_locked and key not in ("enabled",):
            return  # locked — only toggle enabled is allowed
        if widget_id in self._widget_settings:
            # Coerce numeric types for clean storage
            if key in ("width", "height", "refresh_hz", "border_radius", "x", "y"):
                value = int(value)
            elif key in ("opacity", "font_scale"):
                value = float(value)
            self._widget_settings[widget_id][key] = value
            self.widgetSettingsChanged.emit()
            self.settingsSaveRequested.emit()

    @safe_slot()
    @Slot(str)
    def toggleWidget(self, widget_id: str) -> None:  # noqa: N802
        """Toggle the enabled state of a widget."""
        if widget_id in self._widget_settings:
            self._widget_settings[widget_id]["enabled"] = (
                not self._widget_settings[widget_id]["enabled"]
            )
            self.widgetSettingsChanged.emit()
            self.settingsSaveRequested.emit()

    # -- Batch enable / disable ------------------------------------------------

    def _get_category(self, widget_id: str) -> str:
        """Return the category for a widget ID, or empty string if unknown."""
        return self._WIDGET_CATEGORIES.get(widget_id, "")

    @safe_slot()
    @Slot()
    def enableAllWidgets(self) -> None:  # noqa: N802
        """Enable every widget."""
        for wid in self._widget_settings:
            self._widget_settings[wid]["enabled"] = True
        self.widgetSettingsChanged.emit()
        self.settingsSaveRequested.emit()

    @safe_slot()
    @Slot()
    def disableAllWidgets(self) -> None:  # noqa: N802
        """Disable every widget."""
        for wid in self._widget_settings:
            self._widget_settings[wid]["enabled"] = False
        self.widgetSettingsChanged.emit()
        self.settingsSaveRequested.emit()

    @safe_slot()
    @Slot(str)
    def enableCategory(self, category: str) -> None:  # noqa: N802
        """Enable all widgets matching *category*."""
        for wid in self._widget_settings:
            if self._get_category(wid) == category:
                self._widget_settings[wid]["enabled"] = True
        self.widgetSettingsChanged.emit()
        self.settingsSaveRequested.emit()

    @safe_slot()
    @Slot(str)
    def disableCategory(self, category: str) -> None:  # noqa: N802
        """Disable all widgets matching *category*."""
        for wid in self._widget_settings:
            if self._get_category(wid) == category:
                self._widget_settings[wid]["enabled"] = False
        self.widgetSettingsChanged.emit()
        self.settingsSaveRequested.emit()

    def apply_mode_defaults(self, mode: str) -> None:
        """Enable/disable overlays based on the selected mode."""
        defaults = get_mode(mode).overlay_profile
        if not defaults:
            return
        for widget_id in self._widget_settings:
            was_enabled = self._widget_settings[widget_id].get("enabled", False)
            should_enable = widget_id in defaults
            if was_enabled != should_enable:
                self._widget_settings[widget_id]["enabled"] = should_enable
        self.widgetSettingsChanged.emit()
        self.settingsSaveRequested.emit()

    @safe_slot()
    @Slot(result=int)
    def enabledWidgetCount(self) -> int:  # noqa: N802
        """Return the number of currently enabled widgets."""
        return sum(1 for s in self._widget_settings.values() if s.get("enabled"))

    @safe_slot()
    @Slot(result=int)
    def totalWidgetCount(self) -> int:  # noqa: N802
        """Return the total number of widgets."""
        return len(self._widget_settings)

    # -- Slot-based getters (QML can't access nested dict properties) --------

    @safe_slot()
    @Slot(str, result=bool)
    def isWidgetEnabled(self, widget_id: str) -> bool:  # noqa: N802
        s = self._widget_settings.get(widget_id)
        return bool(s.get("enabled")) if s else False

    @safe_slot()
    @Slot(str, result=int)
    def getWidgetWidth(self, widget_id: str) -> int:  # noqa: N802
        return get_widget_int(self._widget_settings, widget_id, "width", 300)

    @safe_slot()
    @Slot(str, result=int)
    def getWidgetHeight(self, widget_id: str) -> int:  # noqa: N802
        return get_widget_int(self._widget_settings, widget_id, "height", 200)

    @safe_slot()
    @Slot(str, result=float)
    def getWidgetOpacity(self, widget_id: str) -> float:  # noqa: N802
        return get_widget_float(self._widget_settings, widget_id, "opacity", 0.92)

    @safe_slot()
    @Slot(str, result=float)
    def getWidgetFontScale(self, widget_id: str) -> float:  # noqa: N802
        return get_widget_float(self._widget_settings, widget_id, "font_scale", 1.0)

    @safe_slot()
    @Slot(str, result=int)
    def getWidgetRefreshHz(self, widget_id: str) -> int:  # noqa: N802
        return get_widget_int(self._widget_settings, widget_id, "refresh_hz", 60)

    @safe_slot()
    @Slot(str, result=int)
    def getWidgetBorderRadius(self, widget_id: str) -> int:  # noqa: N802
        return get_widget_int(self._widget_settings, widget_id, "border_radius", 12)

    @safe_slot()
    @Slot(str, result=float)
    def getWidgetScale(self, widget_id: str) -> float:  # noqa: N802
        return get_widget_float(self._widget_settings, widget_id, "scale", 1.0)

    @safe_slot()
    @Slot(str, float)
    def setWidgetScale(self, widget_id: str, scale: float) -> None:  # noqa: N802
        """Set scale — proportionally adjusts width/height/border_radius from defaults."""
        if self._overlay_locked:
            return
        if widget_id not in self._widget_settings:
            return
        scaled = compute_scaled_widget(self._widget_defaults.get(widget_id, {}), scale)
        self._widget_settings[widget_id].update(scaled)
        self.widgetSettingsChanged.emit()
        self.settingsSaveRequested.emit()

    @safe_slot()
    @Slot(int)
    def toggleWidgetByIndex(self, index: int) -> None:  # noqa: N802
        """Toggle the Nth enabled-capable widget (1-based, for keyboard shortcuts)."""
        ids = list(self._widget_settings.keys())
        if 0 < index <= len(ids):
            wid = ids[index - 1]
            self._widget_settings[wid]["enabled"] = not self._widget_settings[wid]["enabled"]
            self.widgetSettingsChanged.emit()
            self.settingsSaveRequested.emit()

    @safe_slot()
    @Slot(str, result="QVariant")
    def getWidgetSettingsMap(self, widget_id: str) -> dict:  # noqa: N802
        """Return a single widget's full settings as a flat dict."""
        return dict(self._widget_settings.get(widget_id, {}))

    @safe_slot()
    @Slot(result="QVariant")
    def getEnabledWidgetIds(self) -> list:  # noqa: N802
        """Return list of widget IDs that are currently enabled."""
        return [wid for wid, s in self._widget_settings.items() if s.get("enabled")]

    @safe_slot()
    @Slot(result="QVariant")
    def getAllWidgetIds(self) -> list:  # noqa: N802
        """Return list of all widget IDs."""
        return list(self._widget_settings.keys())

    @safe_slot()
    @Slot(int)
    def applyOverlayFlags(self, hwnd: int) -> None:  # noqa: N802
        """Apply TOPMOST + NOACTIVATE flags to overlay windows.

        If hwnd is 0, applies to ALL overlay windows in this process.
        Called from QML after OverlayWidget windows are created.
        Ensures overlays stay above borderless-fullscreen sims.
        """
        if hwnd == 0:
            count = apply_overlay_flags_to_all_overlays()
            log.debug("Applied overlay flags to %d windows", count)
        else:
            apply_overlay_flags(hwnd)

    @safe_slot()
    @Slot(int)
    def removeOverlayFlags(self, hwnd: int) -> None:  # noqa: N802
        """Remove overlay flags (restore normal window behavior)."""
        remove_overlay_flags(hwnd)

    @safe_slot()
    @Slot(str)
    def resetWidget(self, widget_id: str) -> None:  # noqa: N802
        """Reset a widget's settings to factory defaults."""
        if self._overlay_locked:
            return
        if widget_id in self._widget_defaults:
            self._widget_settings[widget_id] = dict(self._widget_defaults[widget_id])
            self.widgetSettingsChanged.emit()
            self.settingsSaveRequested.emit()

    @safe_slot()
    @Slot(str)
    def centerWidget(self, widget_id: str) -> None:  # noqa: N802
        """Move a widget to the center of the primary screen."""
        try:
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            geo = screen.geometry()
            s = self._widget_settings.get(widget_id, {})
            w = s.get("width", 300)
            h = s.get("height", 200)
            self._widget_settings[widget_id]["x"] = geo.x() + (geo.width() - w) // 2
            self._widget_settings[widget_id]["y"] = geo.y() + (geo.height() - h) // 2
            self.widgetSettingsChanged.emit()
            self.settingsSaveRequested.emit()
        except Exception:
            pass

    @safe_slot()
    @Slot()
    def resetAllPositions(self) -> None:  # noqa: N802
        """Reset all widget positions to cascade defaults."""
        idx = 0
        for wid in self._widget_settings:
            self._widget_settings[wid]["x"] = 100 + (idx % 6) * 50
            self._widget_settings[wid]["y"] = 80 + (idx % 6) * 50
            idx += 1
        self.widgetSettingsChanged.emit()
        self.settingsSaveRequested.emit()

    @safe_slot()
    @Slot()
    def autoArrangeOverlays(self) -> None:  # noqa: N802
        """Arrange enabled overlays in a clean grid layout."""
        try:
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            geo = screen.geometry()
            sw, sh = geo.width(), geo.height()
        except Exception:
            sw, sh = 1920, 1080
        enabled = [(wid, s) for wid, s in self._widget_settings.items() if s.get("enabled")]
        if not enabled:
            return
        margin, gap = 20, 12
        x, y, row_h = margin, margin, 0
        for wid, s in enabled:
            w, h = s.get("width", 300), s.get("height", 200)
            if x + w > sw - margin and x > margin:
                x, y, row_h = margin, y + row_h + gap, 0
            s["x"], s["y"] = x, y
            x += w + gap
            row_h = max(row_h, h)
        self.widgetSettingsChanged.emit()
        self.settingsSaveRequested.emit()

    @safe_slot()
    @Slot(str)
    def loadPreset(self, preset_id: str) -> None:  # noqa: N802
        """Apply a layout preset, disabling all widgets first."""
        preset = self._PRESETS.get(preset_id)
        if not preset:
            return
        # Disable every widget
        for wid in self._widget_settings:
            self._widget_settings[wid]["enabled"] = False
        # Apply preset overrides
        for wid, settings in preset.items():
            if wid in self._widget_settings:
                self._widget_settings[wid].update(settings)
        self.widgetSettingsChanged.emit()
        self.settingsSaveRequested.emit()

    @safe_slot()
    @Slot(result="QVariant")
    def getPresetList(self) -> list:  # noqa: N802
        """Return the list of available layout presets for QML."""
        return list(PRESET_LIST)

    @safe_slot()
    @Slot(str, result=int)
    def getWidgetX(self, widget_id: str) -> int:  # noqa: N802
        return get_widget_int(self._widget_settings, widget_id, "x", 100)

    @safe_slot()
    @Slot(str, result=int)
    def getWidgetY(self, widget_id: str) -> int:  # noqa: N802
        return get_widget_int(self._widget_settings, widget_id, "y", 80)

    def export_settings(self) -> dict[str, dict]:
        """Return a serialisable copy of all widget settings for persistence."""
        return {wid: dict(s) for wid, s in self._widget_settings.items()}

    @safe_slot()
    @Slot(str, int, int, result="QVariant")
    def clampToScreen(self, widget_id: str, x: int, y: int) -> dict:  # noqa: N802
        """Clamp x/y so overlay is visible on at least one monitor."""
        try:
            from PySide6.QtCore import QPoint
            from PySide6.QtWidgets import QApplication
            screens = QApplication.screens()
            if not screens:
                return {"x": x, "y": y}
            point = QPoint(x + 50, y + 20)
            for screen in screens:
                if screen.geometry().contains(point):
                    return {"x": x, "y": y}
            primary = QApplication.primaryScreen()
            geo = primary.geometry()
            w = self._widget_settings.get(widget_id, {}).get("width", 300)
            h = self._widget_settings.get(widget_id, {}).get("height", 200)
            return {"x": geo.x() + (geo.width() - w) // 2, "y": geo.y() + (geo.height() - h) // 2}
        except Exception:
            return {"x": x, "y": y}

    @safe_slot()
    @Slot(result="QVariant")
    def getScreenInfo(self) -> list:  # noqa: N802
        """Return info about all connected monitors."""
        try:
            from PySide6.QtWidgets import QApplication
            return [{"name": s.name(), "width": s.geometry().width(), "height": s.geometry().height()}
                    for s in QApplication.screens()]
        except Exception:
            return []

    @safe_slot()
    @Slot(result=str)
    @Slot()
    def copyLayoutToClipboard(self) -> None:  # noqa: N802
        """Export layout to system clipboard as JSON."""
        import json
        from PySide6.QtWidgets import QApplication
        text = json.dumps(self.export_settings(), indent=2)
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    @safe_slot()
    @Slot(result=bool)
    def pasteLayoutFromClipboard(self) -> bool:  # noqa: N802
        """Import layout from system clipboard JSON."""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        if not clipboard:
            return False
        text = clipboard.text()
        return self.importLayoutJson(text) if text else False

    def exportLayoutJson(self) -> str:  # noqa: N802
        """Export current overlay layout as JSON string for sharing."""
        import json
        return json.dumps(self.export_settings(), indent=2)

    @safe_slot()
    @Slot(str, result=bool)
    def importLayoutJson(self, json_str: str) -> bool:  # noqa: N802
        """Import overlay layout from JSON string."""
        import json
        try:
            data = json.loads(json_str)
            if not isinstance(data, dict):
                return False
            for wid, settings in data.items():
                if wid in self._widget_settings and isinstance(settings, dict):
                    self._widget_settings[wid].update(settings)
            self.widgetSettingsChanged.emit()
            self.settingsSaveRequested.emit()
            return True
        except Exception:
            return False

    # -- public API ------------------------------------------------------------

    @safe_slot()
    def update_from_snapshot(self, snap: dict) -> None:
        """Read a coordinator snapshot and update all overlay properties."""
        if not isinstance(snap, dict):
            return
        live = snap.get("live") or {}

        # Telemetry inputs
        try:
            inputs = extract_telemetry_inputs(live)
        except (KeyError, TypeError, ValueError):
            return
        self._speed_kph = inputs.get("speed_kph", 0.0)
        self._throttle_pct = inputs.get("throttle_pct", 0.0)
        self._brake_pct = inputs.get("brake_pct", 0.0)
        self._steering_deg = inputs.get("steering_deg", 0.0)
        self._lat_accel_g = inputs.get("lat_accel_g", 0.0)
        self._long_accel_g = inputs.get("long_accel_g", 0.0)
        self._clutch_pct = inputs.get("clutch_pct", 0.0)
        self._lap_dist_pct = inputs.get("lap_dist_pct", 0.0)
        self._lap_progress = self._lap_dist_pct * 100.0
        self._lap_number = inputs.get("lap_number", 0)
        self._gear = inputs.get("gear", 0)
        self._rpm = inputs.get("rpm", 0)
        self._position = inputs.get("position", 0)
        self._num_cars = inputs.get("num_cars", 0)

        self._tyre_temp_avg = calc_tyre_temp_avg(live)
        self._brake_temp_max = calc_brake_temp_max(live)

        self.inputsChanged.emit()

        # Live telemetry processor -- delta, timing, sectors, detections
        result = self._processor.process(live, snap)
        self._lockup_active = bool(result.get("lockup_active", False))
        self._wheelspin_active = bool(result.get("wheelspin_active", False))
        self._input_smoothness = float(result.get("input_smoothness", 0.75))
        self._live_delta = float(result.get("live_delta_s", 0.0))
        self._current_lap_time = result.get("current_lap_time_fmt", "")

        # Coaching cards — show highest-severity card
        cards = result.get("coaching_cards", [])
        if cards:
            self._coaching_cards = cards
            cinfo = extract_coaching_top_card(cards)
            self._coaching_visible = cinfo["visible"]
            self._coaching_headline = cinfo["headline"]
            self._coaching_sub = cinfo["sub"]
            self._coaching_category = cinfo["category"]
            self._coaching_severity = cinfo["severity"]
            self._coaching_confidence = cinfo["confidence"]
            self._coaching_sector = cinfo["sector"]
            self.coachingChanged.emit()
        elif self._coaching_visible:
            self._coaching_visible = False
            self.coachingChanged.emit()

        # Use processor output for best/last when available, keep
        # existing values as fallback so the overlay never blanks out.
        best_fmt = result.get("best_lap_time_fmt", "")
        if best_fmt:
            self._best_time = best_fmt
        last_fmt = result.get("last_lap_time_fmt", "")
        if last_fmt:
            self._last_time = last_fmt
        # Corner analysis rows
        self._corner_rows = result.get("corner_rows", [])
        self.deltaChanged.emit()

        # Tire state from processor
        ts = result.get("tire_state", {})
        if ts:
            self._tire_grip_pct = float(ts.get("grip_pct", 100))
            self._tire_lap_count = int(ts.get("lap_count", 0))
            self._tire_laps_remaining = int(ts.get("laps_remaining", 99))
            self._tire_condition = str(ts.get("condition", "good"))
            self._tire_temp_lf = float(ts.get("avg_temp_lf", 0))
            self._tire_temp_rf = float(ts.get("avg_temp_rf", 0))
            self._tire_temp_lr = float(ts.get("avg_temp_lr", 0))
            self._tire_temp_rr = float(ts.get("avg_temp_rr", 0))
            self.tireChanged.emit()

        # Sector states
        raw_sectors = result.get("sector_rows", [])
        new_sectors = build_sector_states(raw_sectors, self._lap_dist_pct)
        if new_sectors != self._sector_states:
            self._sector_states = new_sectors
            self.timesChanged.emit()

        # Sector delta scalars for the sector_delta widget (Part 2 plumbing).
        # Extract [delta_s1, delta_s2, delta_s3] — None entries stay None
        # so the widget can render "—" per cell instead of a misleading 0.
        new_deltas: list[float | None] = []
        for row in raw_sectors[:3]:
            d = row.get("delta_s") if isinstance(row, dict) else None
            new_deltas.append(float(d) if isinstance(d, (int, float)) else None)
        # Pad to 3 entries so QML always has a stable shape
        while len(new_deltas) < 3:
            new_deltas.append(None)
        if new_deltas != getattr(self, "_sector_deltas", None):
            self._sector_deltas = new_deltas
            # timesChanged already emitted above if sector_states changed;
            # emit here too in case sectors are identical but deltas changed
            self.timesChanged.emit()

        # Context
        ctx = extract_context(live, snap)
        self._track = ctx["track"]
        self._car = ctx["car"]
        self._is_recording = ctx["is_recording"]
        if self._is_recording:
            self._has_been_recording = True
        self._session_type = ctx["session_type"]
        self._track_length_m = ctx["track_length_m"]
        self._track_temp = ctx["track_temp"]
        self._air_temp = ctx["air_temp"]
        self._current_flag = ctx["current_flag"]

        # Auto-hide: only hide overlays if we WERE recording and then stopped.
        # If no session has started yet, always show overlays.
        if self._auto_hide_enabled and not self._is_recording and self._has_been_recording:
            self._should_show_overlays = False
        else:
            self._should_show_overlays = True

        self.contextChanged.emit()

        # Fuel calculation
        fuel = float(live.get("fuel_level", 0.0))
        if fuel > 0:
            fs = calc_fuel_state(
                fuel, self._prev_fuel_level, self._lap_fuel_samples,
                self._lap_number, int(snap.get("total_laps", 0)),
            )
            self._fuel_level = fs["fuel_level"]
            self._fuel_per_lap = fs["fuel_per_lap"]
            self._fuel_laps_left = fs["fuel_laps_left"]
            self._fuel_state = fs["fuel_state"]
            self._prev_fuel_level = fs["prev_fuel_level"]
            self._lap_fuel_samples = fs["lap_fuel_samples"]
            self.fuelChanged.emit()

        # Live strategy recalculation on lap transitions
        if (
            self._strategy is not None
            and self._is_recording
            and self._lap_number != self._strategy_prev_lap
            and self._lap_number > 0
        ):
            self._strategy_prev_lap = self._lap_number
            self.recalculateLiveStrategy()

        # -- Corner-level technique coaching ----------------------------------
        # Forward per-corner insights into the strategy VM once per lap
        # finalisation so the coaching plan can focus on the dominant corner.
        insights_lap = result.get("corner_insights_lap")
        if (
            insights_lap is not None
            and insights_lap != self._technique_last_pushed_lap
        ):
            insights = result.get("corner_insights") or []
            # T152: surface the worst-corner prompt independently
            # of the strategy-VM forward (works in tests and any
            # configuration without a strategy_vm wired in).
            self._refresh_corner_prompt(insights)
            if self._strategy_vm is not None:
                try:
                    self._strategy_vm.push_corner_insights(insights)
                except Exception:
                    log.debug("push_corner_insights failed", exc_info=True)
            self._technique_last_pushed_lap = insights_lap

        # Advance the pit-call state machine — deterministic source for
        # pit_countdown + strategy_status. Runs before the coaching
        # surface refresh so any state-driven severity changes are
        # reflected in the coaching suppression decision.
        is_in_pits_now = bool(live.get("is_in_pits") or snap.get("is_in_pits") or False)
        new_pit_state = advance_pit_call_state(
            self._pit_call_state,
            laps_to_pit=self.lapsToPit,
            is_in_pits=is_in_pits_now,
            was_in_pits=self._was_in_pits_prev,
        )
        if new_pit_state != self._pit_call_state:
            self._pit_call_state = new_pit_state
            self.strategyChanged.emit()
        self._was_in_pits_prev = is_in_pits_now

        # Refresh the coaching surface state via the policy engine so
        # visibility / cooldown / anti-oscillation kick in.
        raw_now = snap.get("session_time_s") or live.get("session_time_s")
        try:
            now_s = float(raw_now) if raw_now is not None else 0.0
        except (TypeError, ValueError):
            now_s = 0.0
        self._refresh_coaching_surface(now_s=now_s)

        # -- Relative / gap timing (Part 1 plumbing) --------------------------
        self._apply_relative(snap.get("relative"))

        # -- Sector delta extraction (Part 2 plumbing) ------------------------
        # Called only when processor result is available in this method's scope
        # (see _apply_sector_deltas for the extraction logic).

    def _refresh_coaching_surface(self, *, now_s: float) -> None:
        """Re-compute the policy-governed coaching surface state.

        Pulls the unified ``coachingMessage`` dict from the strategy VM
        (same contract all surfaces consume) and feeds it through the
        policy engine. Emits ``coachingChanged`` only when the state
        actually changes so QML bindings don't re-render every tick.
        """
        message = self._build_coaching_message()
        critical = bool(self.pitNow) or self.strategyStatusSeverity == "critical"
        next_state = compute_surface_state(
            previous=self._coaching_surface,
            message=message,
            critical_alert=critical,
            now_s=now_s,
            config=RACE_OVERLAY_POLICY,
        )
        if next_state != self._coaching_surface:
            self._coaching_surface = next_state
            self.coachingChanged.emit()

    def _build_coaching_message(self) -> CoachingMessage:
        """Build the unified CoachingMessage for the overlay surface.

        Calls the strategy VM's ``build_coaching_message`` helper
        directly with ``RACE_OVERLAY_POLICY`` — no dict round-trip, no
        type-coercion loss. Falls back to reconstructing from the
        ``coachingMessage`` dict only for test mocks that predate the
        helper method.
        """
        vm = self._strategy_vm
        if vm is None:
            return CoachingMessage()
        builder = getattr(vm, "build_coaching_message", None)
        if callable(builder):
            try:
                return builder(config=RACE_OVERLAY_POLICY)
            except Exception:
                log.debug("build_coaching_message failed", exc_info=True)
                return CoachingMessage()
        # Mock-only fallback: reconstruct from the dict @Property.
        raw = getattr(vm, "coachingMessage", None)
        if not isinstance(raw, dict):
            return CoachingMessage()
        return CoachingMessage(
            focus_id=str(raw.get("focus_id") or ""),
            category=str(raw.get("category") or ""),
            headline=str(raw.get("headline") or ""),
            subline=str(raw.get("subline") or ""),
            confidence=str(raw.get("confidence") or "low"),
            severity=str(raw.get("severity") or "ok"),
            time_loss_s=raw.get("time_loss_s"),
            supporting=dict(raw.get("supporting") or {}),
        )

    def _apply_relative(self, relative: dict | None) -> None:
        """Populate gap_ahead_s / gap_behind_s / position_{ahead,behind}.

        Only emits contextChanged when values actually change, so repeat
        snapshots with identical relative data don't trigger spurious
        UI repaints. NaN signals "unknown" to QML.
        """
        if not relative or not isinstance(relative, dict):
            new_ahead = float("nan")
            new_behind = float("nan")
            new_pos_ahead = 0
            new_pos_behind = 0
        else:
            def _f(key: str) -> float:
                v = relative.get(key)
                return float(v) if isinstance(v, (int, float)) else float("nan")

            def _i(key: str) -> int:
                v = relative.get(key)
                return int(v) if isinstance(v, (int, float)) and v > 0 else 0

            new_ahead = _f("gap_ahead_s")
            new_behind = _f("gap_behind_s")
            new_pos_ahead = _i("position_ahead")
            new_pos_behind = _i("position_behind")

        # Compare (NaN-aware — NaN != NaN, so use repr for change detection)
        def _same(a: float, b: float) -> bool:
            # Both NaN counts as "same" for change-detection purposes
            import math
            if math.isnan(a) and math.isnan(b):
                return True
            return a == b

        prev_ahead = getattr(self, "_gap_ahead_s", float("nan"))
        prev_behind = getattr(self, "_gap_behind_s", float("nan"))
        changed = (
            not _same(prev_ahead, new_ahead)
            or not _same(prev_behind, new_behind)
            or getattr(self, "_position_ahead", 0) != new_pos_ahead
            or getattr(self, "_position_behind", 0) != new_pos_behind
        )

        self._gap_ahead_s = new_ahead
        self._gap_behind_s = new_behind
        self._position_ahead = new_pos_ahead
        self._position_behind = new_pos_behind

        if changed:
            self.contextChanged.emit()

    @safe_slot()
    @Slot(str)
    def injectSmokeState(self, scenario: str) -> None:  # noqa: N802
        """Debug: inject representative widget state for smoke validation.

        Not for production. Called from the overlay manager's
        "Smoke test" button. Scenarios:

          - "pit_advisory"  → laps_to_pit=3, fuel SAFE
          - "pit_now"       → laps_to_pit=1, fuel SAFE
          - "box_box_box"   → laps_to_pit=0, fuel SAFE
          - "fuel_deficit"  → fuel DEFICIT, strategy_status turns red
          - "sector_delta"  → sectorDeltas=[-0.2, +0.3, null]
          - "gap_available" → gap_ahead=1.2s P4, gap_behind=0.8s P6
          - "gap_missing"   → gaps NaN, widget renders degraded
          - "push_manage_save" → state=SAVE
          - "clear"         → reset all injected state
        """
        if scenario == "pit_advisory":
            self._mock_pit_state(laps_to_pit=3, pit_fuel=40.0)
        elif scenario == "pit_now":
            self._mock_pit_state(laps_to_pit=1, pit_fuel=40.0)
        elif scenario == "box_box_box":
            self._mock_pit_state(laps_to_pit=0, pit_fuel=40.0)
        elif scenario == "fuel_deficit":
            self._mock_fuel_state(margin=-1.5)
        elif scenario == "sector_delta":
            self._sector_deltas = [-0.2, 0.3, None]
            self.timesChanged.emit()
        elif scenario == "gap_available":
            self._gap_ahead_s = 1.2
            self._gap_behind_s = 0.8
            self._position_ahead = 4
            self._position_behind = 6
            self.contextChanged.emit()
        elif scenario == "gap_missing":
            self._gap_ahead_s = float("nan")
            self._gap_behind_s = float("nan")
            self._position_ahead = 0
            self._position_behind = 0
            self.contextChanged.emit()
        elif scenario == "push_manage_save":
            self._mock_fuel_state(margin=0.2)
        elif scenario == "coaching_live":
            # Live high-confidence coaching surface (race_reminder widget)
            self._coaching_surface = SurfaceState(
                message=CoachingMessage(
                    focus_id="T5",
                    category="corner",
                    headline="T5: Braking begins later than your best",
                    subline="Brake 10m earlier, smoother release",
                    confidence="high",
                    severity="positive",
                    time_loss_s=0.35,
                ),
                visible=True,
                freshness="live",
                last_update_s=0.0,
            )
            self.coachingChanged.emit()
        elif scenario == "coaching_carryover":
            self._coaching_surface = SurfaceState(
                message=CoachingMessage(
                    focus_id="T7",
                    category="corner",
                    headline="T7: Throttle pickup is delayed",
                    subline="Get on throttle earlier",
                    confidence="high",
                    severity="positive",
                    time_loss_s=0.25,
                ),
                visible=True,
                freshness="carryover",
                last_update_s=30.0,
            )
            self.coachingChanged.emit()
        elif scenario == "coaching_suppressed":
            # Empty surface — simulates critical-alert suppression
            self._coaching_surface = SurfaceState(visible=False, freshness="stale")
            self.coachingChanged.emit()
        elif scenario == "clear":
            self._sector_deltas = []
            self._gap_ahead_s = float("nan")
            self._gap_behind_s = float("nan")
            self._position_ahead = 0
            self._position_behind = 0
            self._coaching_surface = SurfaceState()
            self._pit_call_state = PitCallState()
            self._was_in_pits_prev = False
            self.timesChanged.emit()
            self.contextChanged.emit()
            self.strategyChanged.emit()
            self.coachingChanged.emit()

    def _mock_pit_state(self, laps_to_pit: int, pit_fuel: float) -> None:
        """Smoke helper: fake a strategy VM that reports a pit lap soon."""
        # Emit strategyChanged so derived properties recompute; the
        # strategy VM stays unchanged — QML bindings re-read via property.
        self._strategy_next_pit_lap = self._lap_number + laps_to_pit
        self._strategy_fuel_to_add = pit_fuel
        self.strategyChanged.emit()

    def _mock_fuel_state(self, margin: float) -> None:
        """Smoke helper: set internal fuel state to trigger a specific band."""
        # Synthesize a burn that produces the desired margin given lap 1/20
        if self._strategy_total_laps <= 0:
            self._strategy_total_laps = 20
        remaining_laps = max(1, self._strategy_total_laps - self._lap_number)
        # For the VM's fuelMargin calculation: margin = current_fuel - remaining_laps * burn
        # We override the strategy-VM-backed fuelMargin by setting a mock attr
        # that takes precedence in the property getter below.
        self._mock_fuel_margin_l = margin
        self.strategyChanged.emit()

    @safe_slot()
    @Slot()
    def dismissCoaching(self) -> None:
        """Dismiss the current coaching card."""
        if self._coaching_cards:
            self._coaching_cards.pop(0)
        cinfo = extract_coaching_top_card(self._coaching_cards)
        self._coaching_visible = cinfo["visible"]
        self._coaching_headline = cinfo["headline"]
        self._coaching_sub = cinfo["sub"]
        self._coaching_category = cinfo["category"]
        self._coaching_severity = cinfo["severity"]
        self._coaching_confidence = cinfo["confidence"]
        self._coaching_sector = cinfo["sector"]
        self.coachingChanged.emit()
