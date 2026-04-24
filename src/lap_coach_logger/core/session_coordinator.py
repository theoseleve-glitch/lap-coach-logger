"""Session lifecycle coordinator.

Bridges the process watcher, adapter, state machine, in-memory
sample buffer, and session finalizer into a single coherent flow:

    sim detected
    → connect adapter → waiting_for_valid_session
    → valid session detected → arming
    → first valid telemetry sample → recording
    → session ends / data freezes / sim lost → finalizing
    → save ok → ready_for_review → waiting_for_valid_session / idle
    → save failed / runtime faults → failed

Key robustness features:
  - *Data-freeze detection*: if the ``raw_source_timestamp`` (or
    ``packetId``) does not change for ``data_freeze_timeout_s`` the
    session is considered stale.
  - *Debounce / cooldown*: after finalization the coordinator waits
    ``cooldown_after_finalize_s`` before accepting a new session to
    avoid duplicate outputs from rapid session transitions.
  - *Minimum-save filter*: sessions shorter than ``min_duration_s``
    or with fewer than ``min_samples_to_save`` samples are discarded
    instead of saved.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from lap_coach_logger.adapters.base import SimAdapter
from lap_coach_logger.config.models import ACCConfig, AppConfig, AssettoCorsaConfig, IRacingConfig, LMUConfig
from lap_coach_logger.core.ghost_reference import GhostReference
from lap_coach_logger.core.ghost_tracker import GhostDelta, GhostTracker
from lap_coach_logger.core.health import HealthMonitor
from lap_coach_logger.core.iracing_raw_capture import IRacingRawCapture
from lap_coach_logger.core.lap_analysis import classify_laps
from lap_coach_logger.core.live_coach import LiveCoachTracker
from lap_coach_logger.core.live_input_diagnostics import LiveInputDiagnosticsTracker
from lap_coach_logger.core.live_platform_analysis import LivePlatformAnalysisTracker
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.session_state import SessionState, SessionStateMachine
from lap_coach_logger.utils.shutdown import shutdown_requested
from lap_coach_logger.writers.bundle_schema import (
    LegacyLapRecord as LapRecord,
    SessionEvent,
)
from lap_coach_logger.writers.finalizer import SessionFinalizer

log = logging.getLogger(__name__)

# Hard cap: discard oldest samples if buffer exceeds this to prevent OOM
_MAX_BUFFER_SAMPLES = 500_000  # ~50 min at 10 Hz ≈ 120 MB RAM
_MAX_RAW_BUFFER_SAMPLES = 2_000_000  # raw capture at higher SDK rates
# Require stable session activity before transitioning to ARMING.
_ACTIVE_POLLS_TO_START = 2
# If a session becomes active but no valid sample arrives, fail arming.
_ARMING_TIMEOUT_S = 5.0


class SessionCoordinator:
    """Owns the recording lifecycle for one sim at a time."""

    def __init__(self, config: AppConfig, health: HealthMonitor | None = None) -> None:
        self._config = config
        self._fsm = SessionStateMachine()
        self._finalizer = SessionFinalizer(
            config.output_path,
            compression=config.writer.parquet_compression,
            debug_csv_export=config.writer.debug_csv_export,
            quality_config=config.quality,
        )
        self._health = health or HealthMonitor()
        self._buffer: list[TelemetrySample] = []
        self._active_adapter: SimAdapter | None = None
        self._session_started_at: datetime | None = None
        self._session_uid: str | None = None
        self._dropped_samples: int = 0
        self._latest_sample: TelemetrySample | None = None
        self._latest_dashboard_state: dict[str, Any] = {}
        self._derived_dashboard_state: dict[str, Any] = {}
        self._live_coach = LiveCoachTracker()
        self._live_input_diagnostics = LiveInputDiagnosticsTracker()
        self._live_platform_analysis = LivePlatformAnalysisTracker()
        # Ghost coaching overlay
        self._ghost_tracker: GhostTracker | None = None
        self._ghost_reference: GhostReference | None = None
        self._latest_ghost_delta: GhostDelta | None = None
        self._events: list[SessionEvent] = []
        self._record_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._monitoring = False
        self._waiting_active_polls: int = 0
        self._arming_started_at: float | None = None
        self._current_lap_number: int | None = None
        self._current_lap_start_session_time_s: float | None = None
        self._current_lap_start_fuel_level: float | None = None
        self._last_lap_time_s: float | None = None
        self._best_lap_time_s: float | None = None
        self._fuel_burn_per_lap: list[float] = []
        self._sector_count: int = 3
        self._current_sector_markers: dict[int, float] = {}
        self._current_sector_splits: dict[int, float] = {}
        self._last_sector_splits: dict[int, float] = {}

        # Data-freeze tracking
        self._last_raw_ts: float | None = None
        self._last_raw_ts_changed_at: float = 0.0

        # Raw capture state
        self._raw_capture: IRacingRawCapture | None = None
        self._raw_capture_sim: str | None = None
        self._raw_var_schema: list[dict[str, Any]] | None = None

    # -- properties --------------------------------------------------------

    @property
    def state(self) -> SessionState:
        return self._fsm.state

    @property
    def sample_count(self) -> int:
        return len(self._buffer)

    @property
    def health(self) -> HealthMonitor:
        return self._health

    @property
    def is_monitoring(self) -> bool:
        return self._monitoring

    @property
    def session_started_at(self) -> datetime | None:
        return self._session_started_at

    def latest_relative_snapshot(self) -> dict[str, object] | None:
        """Return the active adapter's read_relative() output, or None.

        Safe to call from UI thread — catches all exceptions so a flaky
        SDK can never break the snapshot pipeline.
        """
        adapter = self._active_adapter
        if adapter is None:
            return None
        try:
            return adapter.read_relative()
        except Exception:
            return None

    def latest_sample_snapshot(self) -> dict[str, object]:
        """Return a shallow dict snapshot of the latest sample for UI display."""
        with self._lock:
            sample = self._latest_sample.to_dict() if self._latest_sample is not None else {}
            dashboard = dict(self._latest_dashboard_state)
            derived = dict(self._derived_dashboard_state)
            if not sample and not dashboard and not derived:
                return {}
        snapshot: dict[str, object] = dict(sample)
        snapshot.update(dashboard)
        snapshot.update(derived)
        return snapshot

    def live_coaching_snapshot(self) -> dict[str, object]:
        """Return the latest coaching and alert state for lap_pc."""
        with self._lock:
            return dict(self._live_coach.snapshot())

    def hardware_diagnostics_snapshot(self) -> dict[str, object]:
        """Return the latest input and FFB diagnostics for lap_pc."""
        with self._lock:
            return dict(self._live_input_diagnostics.snapshot())

    def platform_analysis_snapshot(self) -> dict[str, object]:
        """Return the latest ride-height and aero-platform diagnostics for lap_pc."""
        with self._lock:
            return dict(self._live_platform_analysis.snapshot())

    def ghost_coaching_snapshot(self) -> dict[str, object]:
        """Return the latest ghost delta for the overlay."""
        with self._lock:
            delta = self._latest_ghost_delta
            if delta is None:
                return {}
            return {
                "ghost_speed_delta_kph": round(delta.speed_delta_kph, 1),
                "ghost_throttle_delta_pct": round(delta.throttle_delta_pct, 3),
                "ghost_brake_delta_pct": round(delta.brake_delta_pct, 3),
                "ghost_steering_delta_deg": round(delta.steering_delta_deg, 1),
                "ghost_cumulative_delta_s": round(delta.cumulative_delta_s, 3),
                "ghost_theoretical_speed_kph": round(delta.theoretical_speed_kph, 1),
                "ghost_theoretical_throttle_pct": round(delta.theoretical_throttle_pct, 3),
                "ghost_theoretical_brake_pct": round(delta.theoretical_brake_pct, 3),
                "ghost_theoretical_steering_deg": round(delta.theoretical_steering_deg, 1),
                "ghost_loaded": True,
            }

    # -- detection callbacks (called from ProcessWatcher) ------------------

    def _transition(self, target: SessionState, *, reason: str, event: str | None = None) -> bool:
        """Single transition gateway used by coordinator logic."""
        changed = self._fsm.transition(target, reason=reason, event=event)
        if changed:
            self._health.update(state=target.value)
        return changed

    def _record_event(self, event: str, detail: dict[str, Any] | None = None) -> None:
        """Append a timestamped lifecycle event."""
        self._events.append(SessionEvent(
            event=event,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            detail=detail,
        ))

    def on_sim_found(self, adapter: SimAdapter, _detected: bool) -> bool:
        """React to a sim process appearing."""
        with self._lock:
            if self._fsm.state != SessionState.IDLE:
                return False
            self._transition(
                SessionState.SIMULATOR_DETECTED,
                reason="sim process detected",
                event="sim_detected",
            )
            self._active_adapter = adapter
            self._health.update(sim=adapter.sim_name, last_error=None)
            self._record_event("simulator_detected", {"sim": adapter.sim_name})

            if adapter.connect():
                self._record_event("adapter_connected", {"sim": adapter.sim_name})
                log.info("Adapter connected — waiting for valid session")
                self._transition(
                    SessionState.WAITING_FOR_VALID_SESSION,
                    reason="adapter connection succeeded",
                    event="adapter_connected",
                )
                self._start_monitor_loop()
                return True
            else:
                log.info("Adapter not ready yet — returning to IDLE and waiting to retry")
                self._active_adapter = None
                self._transition(
                    SessionState.IDLE,
                    reason="adapter connection failed",
                    event="adapter_connect_failed",
                )
                self._health.update(sim=None)
                return False

    def on_sim_lost(self, _adapter: SimAdapter, _detected: bool) -> None:
        """React to the sim process disappearing."""
        with self._lock:
            self._record_event("sim_lost", {"reason": "sim_process_lost"})
            if self._fsm.state in (SessionState.ARMING, SessionState.RECORDING):
                self._transition(
                    SessionState.FINALIZING,
                    reason="simulator closed unexpectedly",
                    event="sim_lost",
                )
                self._finalize_session()
            elif self._fsm.state in (
                SessionState.SIMULATOR_DETECTED,
                SessionState.WAITING_FOR_VALID_SESSION,
                SessionState.READY_FOR_REVIEW,
            ):
                self._reset()
            self._active_adapter = None
            self._health.update(sim=None, last_error="Simulator closed")

    # -- monitor / recording loop ------------------------------------------

    def _start_monitor_loop(self) -> None:
        """Start the background thread that monitors for sessions and records."""
        if self._record_thread and self._record_thread.is_alive():
            log.warning("Monitor thread already running — skipping duplicate")
            return
        self._monitoring = True
        self._record_thread = threading.Thread(
            target=self._monitor_loop, name="session-monitor", daemon=True
        )
        self._record_thread.start()

    def _monitor_loop(self) -> None:
        """Unified loop that handles waiting → arming → recording → finalizing."""
        adapter = self._active_adapter
        interval = self._config.sample_interval_s
        scfg = self._config.session

        # Determine if we should use tick-driven iRacing capture
        use_tick_driven = (
            adapter is not None
            and adapter.supports_raw_capture()
            and isinstance(self._config.iracing, IRacingConfig)
            and self._config.iracing.sample_mode == "auto_sdk"
        )
        use_raw_capture = (
            adapter is not None
            and adapter.supports_raw_capture()
            and self._raw_capture_enabled(adapter)
        )

        if use_tick_driven:
            log.info("iRacing auto_sdk mode: tick-driven sampling enabled")
        if use_raw_capture:
            log.info("%s raw capture enabled", adapter.sim_name if adapter else "sim")

        while not shutdown_requested():
            state = self._fsm.state
            if adapter is None:
                break

            # ── WAITING_FOR_VALID_SESSION ───────────────────────────
            if state == SessionState.WAITING_FOR_VALID_SESSION:
                try:
                    if self._waiting_activity_confirmed(adapter.is_session_active()):
                        with self._lock:
                            self._begin_arming()
                            if use_raw_capture:
                                self._init_raw_capture(adapter)
                except Exception:
                    log.debug("Error checking session activity", exc_info=True)
                time.sleep(self._config.poll_interval_s)
                continue

            # ── ARMING ───────────────────────────────────────────────
            if state == SessionState.ARMING:
                try:
                    if not adapter.connected:
                        self._record_event("adapter_disconnected", {"phase": "arming"})
                        self._transition(
                            SessionState.FAILED,
                            reason="adapter disconnected while arming",
                            event="adapter_disconnected",
                        )
                        self._health.update(last_error="Adapter disconnected while arming")
                        self._post_finalize()
                        continue

                    if not adapter.is_session_active():
                        self._transition(
                            SessionState.FAILED,
                            reason="session became inactive before telemetry started",
                            event="session_invalid_during_arming",
                        )
                        self._health.update(last_error="Session became inactive before telemetry")
                        self._post_finalize()
                        continue

                    sample = adapter.read_sample()
                    if sample is not None:
                        dashboard_state = self._read_dashboard_state(adapter)
                        self._record_event("recording_started")
                        self._transition(
                            SessionState.RECORDING,
                            reason="first valid telemetry sample received",
                            event="recording_started",
                        )
                        self._append_sample(sample, dashboard_state)
                        # Capture raw alongside if enabled
                        if use_raw_capture:
                            self._capture_raw_sample(adapter)
                            self._capture_session_info(adapter)
                        self._health.update(
                            sample_count=len(self._buffer),
                            dropped_samples=self._dropped_samples,
                            session_started_at=(
                                self._session_started_at.isoformat()
                                if self._session_started_at
                                else None
                            ),
                        )
                    elif self._arming_started_at is not None and (
                        time.monotonic() - self._arming_started_at >= _ARMING_TIMEOUT_S
                    ):
                        self._record_event("recording_stopped", {"reason": "no_valid_telemetry"})
                        self._transition(
                            SessionState.FAILED,
                            reason="session started but no valid telemetry arrived",
                            event="no_valid_telemetry",
                        )
                        self._health.update(last_error="No valid telemetry while arming")
                        self._post_finalize()
                        continue
                except Exception:
                    log.exception("Error in arming loop")

                if use_tick_driven:
                    adapter.wait_for_new_tick(timeout_s=0.5)
                else:
                    time.sleep(interval)
                continue

            # ── RECORDING ────────────────────────────────────────────
            if state == SessionState.RECORDING:
                try:
                    if not adapter.connected:
                        self._record_event("adapter_disconnected", {"phase": "recording"})
                        self._transition(
                            SessionState.FAILED,
                            reason="adapter disconnected mid-session",
                            event="adapter_disconnected",
                        )
                        self._health.update(last_error="Adapter disconnected mid-session")
                        self._end_recording()
                        continue

                    # Check session still active
                    if not adapter.is_session_active():
                        log.info("Session no longer active — grace period (%.1fs)",
                                 self._config.session_end_grace_s)
                        time.sleep(self._config.session_end_grace_s)
                        if not adapter.is_session_active():
                            with self._lock:
                                self._end_recording()
                            continue
                        else:
                            log.info("Session resumed after grace period")
                            continue

                    sample = adapter.read_sample()
                    if sample is not None:
                        dashboard_state = self._read_dashboard_state(adapter)
                        self._append_sample(sample, dashboard_state)

                        # Capture raw alongside if enabled
                        if use_raw_capture:
                            self._capture_raw_sample(adapter)

                        # Update health periodically (every 100 samples)
                        if len(self._buffer) % 100 == 0:
                            self._health.update(
                                sample_count=len(self._buffer),
                                dropped_samples=self._dropped_samples,
                            )

                        # Periodically update session info snapshot
                        if use_raw_capture and len(self._buffer) % 500 == 0:
                            self._capture_session_info(adapter)

                        # Data-freeze detection
                        if self._is_data_frozen(sample, scfg.data_freeze_timeout_s):
                            log.warning("Data frozen for %.1fs — ending session",
                                        scfg.data_freeze_timeout_s)
                            with self._lock:
                                self._end_recording()
                            continue

                except Exception:
                    log.exception("Error in recording loop")

                # Tick-driven wait for iRacing auto_sdk; sleep for others
                if use_tick_driven:
                    adapter.wait_for_new_tick(timeout_s=1.0)
                else:
                    time.sleep(interval)
                continue

            # ── READY_FOR_REVIEW ─────────────────────────────────────
            if state == SessionState.READY_FOR_REVIEW:
                time.sleep(scfg.cooldown_after_finalize_s)
                with self._lock:
                    # If sim is still running, go back to waiting
                    if self._active_adapter is not None:
                        self._transition(
                            SessionState.WAITING_FOR_VALID_SESSION,
                            reason="ready-for-review cooldown elapsed while sim still connected",
                            event="resume_waiting",
                        )
                    else:
                        self._transition(
                            SessionState.IDLE,
                            reason="ready-for-review cooldown elapsed with no active sim",
                            event="return_idle",
                        )
                continue

            # ── Other states (IDLE, FINALIZING, FAILED) — exit loop ──
            break

        # Shutdown while recording/arming → best-effort finalize
        if shutdown_requested() and self._fsm.state in (SessionState.ARMING, SessionState.RECORDING):
            with self._lock:
                self._record_event("recording_stopped", {"reason": "app_shutdown"})
                self._end_recording()

    # -- recording lifecycle -----------------------------------------------

    def _begin_arming(self) -> None:
        log.info("Valid session found — arming recorder")
        self._waiting_active_polls = 0
        self._session_started_at = datetime.now(timezone.utc)
        self._arming_started_at = time.monotonic()
        self._buffer.clear()
        self._session_uid = None
        self._dropped_samples = 0
        self._latest_sample = None
        self._last_raw_ts = None
        self._last_raw_ts_changed_at = time.monotonic()
        self._events.clear()
        self._raw_capture = None
        self._raw_capture_sim = None
        self._raw_var_schema = None
        self._reset_live_state()
        self._record_event("valid_session_found")
        self._transition(
            SessionState.ARMING,
            reason="session activity confirmed",
            event="valid_session_found",
        )
        self._health.update(
            sample_count=0,
            dropped_samples=0,
            session_started_at=self._session_started_at.isoformat(),
            last_error=None,
        )

    def _append_sample(
        self,
        sample: TelemetrySample,
        dashboard_state: dict[str, Any] | None = None,
    ) -> None:
        """Append sample with buffer cap protection."""
        with self._lock:
            self._latest_sample = sample
            self._latest_dashboard_state = dict(dashboard_state or {})
            self._update_live_metrics_locked(sample, self._latest_dashboard_state)
            self._live_coach.push_sample(
                sample,
                dashboard_state=self._latest_dashboard_state,
                derived_state=self._derived_dashboard_state,
            )
            self._live_input_diagnostics.push_sample(
                sample,
                dashboard_state=self._latest_dashboard_state,
                derived_state=self._derived_dashboard_state,
            )
            self._live_platform_analysis.push_sample(
                sample,
                dashboard_state=self._latest_dashboard_state,
                derived_state=self._derived_dashboard_state,
            )
            # Ghost coaching: try to load reference on first sample with track info
            if self._ghost_tracker is None and sample.track_name and sample.car_name:
                try:
                    from pathlib import Path
                    output_dir = Path(self._config.output_path)
                    ref = GhostReference.find_latest(output_dir, sample.track_name, sample.car_name)
                    if ref is not None:
                        self._ghost_reference = ref
                        self._ghost_tracker = GhostTracker(ref)
                        log.info("Ghost loaded for %s / %s (%.3fs)",
                                 ref.track_name, ref.car_name, ref.theoretical_lap_time_s)
                    else:
                        # Set tracker to a sentinel to prevent retrying every sample
                        self._ghost_tracker = False  # type: ignore[assignment]
                except Exception:
                    log.debug("Failed to load ghost reference", exc_info=True)
                    self._ghost_tracker = False  # type: ignore[assignment]

            if isinstance(self._ghost_tracker, GhostTracker):
                ghost_delta = self._ghost_tracker.update(sample)
                if ghost_delta is not None:
                    self._latest_ghost_delta = ghost_delta

            if len(self._buffer) >= _MAX_BUFFER_SAMPLES:
                self._dropped_samples += 1
                if self._dropped_samples % 1000 == 1:
                    log.warning(
                        "Buffer at capacity (%d) — dropping samples (total dropped: %d)",
                        _MAX_BUFFER_SAMPLES, self._dropped_samples,
                    )
                return

            self._buffer.append(sample)
            if self._session_uid is None:
                self._session_uid = sample.session_uid

    def _read_dashboard_state(self, adapter: SimAdapter) -> dict[str, Any]:
        """Read sim-specific dashboard data without failing the monitor loop."""
        try:
            state = adapter.read_dashboard_state()
        except Exception:
            log.debug("Error reading %s dashboard state", adapter.sim_name, exc_info=True)
            return {}
        return dict(state or {})

    def _reset_live_state(self) -> None:
        self._latest_dashboard_state = {}
        self._derived_dashboard_state = {}
        self._live_coach.reset()
        self._live_input_diagnostics.reset()
        self._live_platform_analysis.reset()
        self._ghost_tracker = None
        self._ghost_reference = None
        self._latest_ghost_delta = None
        self._current_lap_number = None
        self._current_lap_start_session_time_s = None
        self._current_lap_start_fuel_level = None
        self._last_lap_time_s = None
        self._best_lap_time_s = None
        self._fuel_burn_per_lap = []
        self._sector_count = 3
        self._current_sector_markers = {}
        self._current_sector_splits = {}
        self._last_sector_splits = {}

    def _update_live_metrics_locked(
        self,
        sample: TelemetrySample,
        dashboard_state: dict[str, Any],
    ) -> None:
        lap_time_s = _positive_float(dashboard_state.get("lap_time_s"))
        last_lap_time_s = _positive_float(dashboard_state.get("last_lap_time_s"))
        best_lap_time_s = _positive_float(dashboard_state.get("best_lap_time_s"))
        fuel_level = _nonnegative_float(
            dashboard_state.get("fuel_level"),
            fallback=sample.fuel_level,
        )
        session_time_s = _nonnegative_float(sample.session_time_s)
        sector_count = _positive_int(dashboard_state.get("sector_count"), fallback=self._sector_count) or 3
        self._sector_count = max(3, sector_count)

        if best_lap_time_s is not None:
            if self._best_lap_time_s is None or best_lap_time_s < self._best_lap_time_s:
                self._best_lap_time_s = best_lap_time_s
        if last_lap_time_s is not None:
            self._last_lap_time_s = last_lap_time_s
            if self._best_lap_time_s is None or last_lap_time_s < self._best_lap_time_s:
                self._best_lap_time_s = last_lap_time_s

        self._update_lap_tracking_locked(
            lap_number=sample.lap_number,
            session_time_s=session_time_s,
            lap_time_s=lap_time_s,
            last_lap_time_s=last_lap_time_s,
            fuel_level=fuel_level,
        )
        self._apply_explicit_sector_splits_locked(dashboard_state)
        self._update_sector_progress_locked(
            current_sector_index=_positive_int(dashboard_state.get("current_sector_index")),
            last_sector_time_s=_positive_float(dashboard_state.get("last_sector_time_s")),
        )

        if lap_time_s is None and session_time_s is not None and self._current_lap_start_session_time_s is not None:
            lap_time_s = max(0.0, session_time_s - self._current_lap_start_session_time_s)

        fuel_per_lap_l = _positive_float(dashboard_state.get("fuel_per_lap_l"))
        if fuel_per_lap_l is None and self._fuel_burn_per_lap:
            fuel_per_lap_l = sum(self._fuel_burn_per_lap) / len(self._fuel_burn_per_lap)

        laps_remaining_est = _positive_float(dashboard_state.get("laps_remaining_est"))
        if laps_remaining_est is None and fuel_level is not None and fuel_per_lap_l and fuel_per_lap_l > 0:
            laps_remaining_est = fuel_level / fuel_per_lap_l

        derived: dict[str, Any] = {}
        if lap_time_s is not None:
            derived["lap_time_s"] = round(lap_time_s, 3)
        if self._last_lap_time_s is not None:
            derived["last_lap_time_s"] = round(self._last_lap_time_s, 3)
        if self._best_lap_time_s is not None:
            derived["best_lap_time_s"] = round(self._best_lap_time_s, 3)
        if fuel_per_lap_l is not None:
            derived["fuel_per_lap_l"] = round(fuel_per_lap_l, 3)
        if laps_remaining_est is not None:
            derived["laps_remaining_est"] = round(laps_remaining_est, 2)
        for idx in range(1, 4):
            split = self._current_sector_splits.get(idx)
            if split is None:
                split = self._last_sector_splits.get(idx)
            if split is not None:
                derived[f"sector_{idx}_time_s"] = round(split, 3)
        self._derived_dashboard_state = derived

    def _update_lap_tracking_locked(
        self,
        *,
        lap_number: int | None,
        session_time_s: float | None,
        lap_time_s: float | None,
        last_lap_time_s: float | None,
        fuel_level: float | None,
    ) -> None:
        if lap_number is None:
            return

        inferred_lap_start = None
        if session_time_s is not None and lap_time_s is not None:
            inferred_lap_start = max(0.0, session_time_s - lap_time_s)

        if self._current_lap_number is None or lap_number < self._current_lap_number:
            self._current_lap_number = lap_number
            self._current_lap_start_session_time_s = (
                inferred_lap_start if inferred_lap_start is not None else session_time_s
            )
            self._current_lap_start_fuel_level = fuel_level
            self._current_sector_markers.clear()
            self._current_sector_splits.clear()
            return

        if lap_number > self._current_lap_number:
            completed_lap_time = last_lap_time_s
            if completed_lap_time is None and session_time_s is not None and self._current_lap_start_session_time_s is not None:
                completed_lap_time = max(0.0, session_time_s - self._current_lap_start_session_time_s)

            if completed_lap_time is not None and completed_lap_time > 0:
                self._last_lap_time_s = completed_lap_time
                if self._best_lap_time_s is None or completed_lap_time < self._best_lap_time_s:
                    self._best_lap_time_s = completed_lap_time

            if (
                fuel_level is not None
                and self._current_lap_start_fuel_level is not None
                and self._current_lap_start_fuel_level >= fuel_level
            ):
                burn = self._current_lap_start_fuel_level - fuel_level
                if burn > 0:
                    self._fuel_burn_per_lap.append(burn)
                    if len(self._fuel_burn_per_lap) > 6:
                        self._fuel_burn_per_lap = self._fuel_burn_per_lap[-6:]

            self._finalize_sector_splits_locked(completed_lap_time)
            self._current_lap_number = lap_number
            self._current_lap_start_session_time_s = (
                inferred_lap_start if inferred_lap_start is not None else session_time_s
            )
            self._current_lap_start_fuel_level = fuel_level
            self._current_sector_markers.clear()
            self._current_sector_splits.clear()
            return

        if self._current_lap_start_session_time_s is None and (inferred_lap_start is not None or session_time_s is not None):
            self._current_lap_start_session_time_s = (
                inferred_lap_start if inferred_lap_start is not None else session_time_s
            )
        if self._current_lap_start_fuel_level is None and fuel_level is not None:
            self._current_lap_start_fuel_level = fuel_level

    def _apply_explicit_sector_splits_locked(self, dashboard_state: dict[str, Any]) -> None:
        for idx in range(1, 4):
            split = _positive_float(dashboard_state.get(f"sector_{idx}_time_s"))
            if split is not None:
                self._current_sector_splits[idx] = split

    def _update_sector_progress_locked(
        self,
        *,
        current_sector_index: int | None,
        last_sector_time_s: float | None,
    ) -> None:
        if current_sector_index is None or last_sector_time_s is None:
            return

        completed_sector = current_sector_index - 1
        if completed_sector < 1 or completed_sector > 3:
            return

        previous_marker = self._current_sector_markers.get(completed_sector - 1, 0.0)
        previous_time = self._current_sector_markers.get(completed_sector)
        if previous_time is not None and abs(previous_time - last_sector_time_s) < 0.001:
            return

        self._current_sector_markers[completed_sector] = last_sector_time_s
        split = last_sector_time_s if completed_sector == 1 else last_sector_time_s - previous_marker
        if split > 0:
            self._current_sector_splits[completed_sector] = split

    def _finalize_sector_splits_locked(self, completed_lap_time: float | None) -> None:
        if completed_lap_time is not None and completed_lap_time > 0 and 2 in self._current_sector_markers:
            sector_three = completed_lap_time - self._current_sector_markers[2]
            if sector_three > 0:
                self._current_sector_splits[3] = sector_three
        if self._current_sector_splits:
            self._last_sector_splits = dict(self._current_sector_splits)

    def _raw_capture_enabled(self, adapter: SimAdapter) -> bool:
        """Return True if raw capture is enabled for the active adapter."""
        if adapter.sim_name == "iRacing":
            return isinstance(self._config.iracing, IRacingConfig) and self._config.iracing.raw_capture_enabled
        if adapter.sim_name == "Assetto Corsa":
            return (
                isinstance(self._config.assetto_corsa, AssettoCorsaConfig)
                and self._config.assetto_corsa.raw_capture_enabled
            )
        if adapter.sim_name == "ACC":
            return isinstance(self._config.acc, ACCConfig) and self._config.acc.raw_capture_enabled
        if adapter.sim_name == "Le Mans Ultimate":
            return isinstance(self._config.lmu, LMUConfig) and self._config.lmu.raw_capture_enabled
        return False

    # -- raw capture helpers -------------------------------------------------

    def _init_raw_capture(self, adapter: SimAdapter) -> None:
        """Set up the raw capture helper for the active adapter."""
        rc = IRacingRawCapture()
        self._raw_capture_sim = adapter.sim_name
        self._raw_var_schema = None

        iracing_cfg = self._config.iracing
        if adapter.sim_name == "iRacing" and isinstance(iracing_cfg, IRacingConfig):
            rc.load_catalogs(
                localserver_track_fields_path=iracing_cfg.catalog_localserver_track_fields,
                localserver_arq_messages_path=iracing_cfg.catalog_localserver_arq_messages,
                sim_param_names_path=iracing_cfg.catalog_sim_param_names,
            )
            # Cache the live var schema for channel metadata
            self._load_iracing_var_schema(iracing_cfg.catalog_live_var_schema)
        self._raw_capture = rc
        log.info("%s raw capture initialized", adapter.sim_name)

    def _load_iracing_var_schema(self, path: str) -> None:
        """Load the live var schema JSON for channel metadata."""
        if not path:
            return
        import json
        from pathlib import Path

        p = Path(path)
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    self._raw_var_schema = json.load(f)
            except Exception:
                log.debug("Could not load iRacing var schema", exc_info=True)

    def _capture_raw_sample(self, adapter: SimAdapter) -> None:
        """Read and buffer one raw sample from the adapter."""
        if self._raw_capture is None:
            return
        if self._raw_capture.raw_sample_count >= _MAX_RAW_BUFFER_SAMPLES:
            return
        raw = adapter.read_raw_sample()
        if raw is not None:
            self._raw_capture.append_raw_sample(raw)

    def _capture_session_info(self, adapter: SimAdapter) -> None:
        """Snapshot the current session info tree."""
        if self._raw_capture is None:
            return
        snapshot = adapter.read_session_info_snapshot()
        if snapshot:
            self._raw_capture.set_session_info_snapshot(snapshot)

    def _end_recording(self) -> None:
        """Transition from recording/arming → finalizing."""
        self._record_event("recording_stopped")
        if self._fsm.state in (SessionState.ARMING, SessionState.RECORDING, SessionState.FAILED):
            self._transition(
                SessionState.FINALIZING,
                reason="recording stop requested",
                event="recording_stopped",
            )
        self._finalize_session()

    def _waiting_activity_confirmed(self, is_active: bool) -> bool:
        """Return True once waiting activity is stable across polls."""
        if not is_active:
            self._waiting_active_polls = 0
            return False
        self._waiting_active_polls += 1
        return self._waiting_active_polls >= _ACTIVE_POLLS_TO_START

    # -- data-freeze detection ---------------------------------------------

    def _is_data_frozen(self, sample: TelemetrySample, timeout: float) -> bool:
        """Return True if the raw timestamp hasn't changed for *timeout* seconds."""
        raw_ts = sample.raw_source_timestamp
        now = time.monotonic()

        if raw_ts is None:
            # No raw timestamp available — can't detect freeze this way
            return False

        if self._last_raw_ts is None or raw_ts != self._last_raw_ts:
            self._last_raw_ts = raw_ts
            self._last_raw_ts_changed_at = now
            return False

        return (now - self._last_raw_ts_changed_at) >= timeout

    # -- finalization ------------------------------------------------------

    def _finalize_session(self) -> None:
        """Write session bundle if thresholds are met, then transition."""
        scfg = self._config.session
        duration = 0.0
        if self._session_started_at:
            duration = (datetime.now(timezone.utc) - self._session_started_at).total_seconds()

        n_samples = len(self._buffer)

        if n_samples == 0:
            self._transition(
                SessionState.FAILED,
                reason="empty session: no telemetry samples captured",
                event="empty_session",
            )
            self._health.update(last_error="No telemetry captured in session")
            self._post_finalize()
            return

        # ── minimum-save filter ──
        if n_samples < scfg.min_samples_to_save or duration < scfg.min_duration_s:
            log.info(
                "Session too short to save (samples=%d, duration=%.1fs) — discarding",
                n_samples,
                duration,
            )
            self._post_finalize()
            return

        first = self._buffer[0]
        lap_records, lap_summary = classify_laps(
            self._buffer,
            config=self._config.lap_analysis,
        )
        max_lap = max((lap.lap_number for lap in lap_records), default=None)

        # Back-compat flat lap_times dict should only include laps with valid durations.
        lap_times = {
            lr.lap_number: lr.lap_time_s
            for lr in lap_records
            if lr.lap_time_valid and lr.lap_time_s is not None
        }
        best_lap = lap_summary.best_lap_time_s

        # ── environment snapshot from first valid sample ──
        env: dict[str, float | None] = {}
        for s in self._buffer:
            if s.track_temp_c is not None or s.air_temp_c is not None:
                env["track_temp_c"] = s.track_temp_c
                env["air_temp_c"] = s.air_temp_c
                break

        self._record_event("finalize_started", {"sample_count": n_samples})

        # Determine adapter name
        adapter_name: str | None = None
        if self._active_adapter is not None:
            adapter_name = type(self._active_adapter).__name__

        result = self._finalizer.finalize(
            self._buffer,
            started_at=self._session_started_at or datetime.now(timezone.utc),
            sim=first.sim,
            track=first.track_name,
            session_type=first.session_type,
            session_uid=self._session_uid,
            laps=lap_records,
            events=list(self._events),
            driver_name=self._config.driver_name or None,
            adapter_name=adapter_name,
            extra_metadata=self._build_extra_metadata(
                duration, max_lap, first, lap_times, best_lap, lap_summary, env
            ),
            raw_capture_sim=self._raw_capture_sim,
            raw_samples=self._raw_capture.raw_buffer if self._raw_capture else None,
            raw_columns=self._raw_capture.get_raw_column_names() if self._raw_capture else None,
            raw_session_info=self._raw_capture.session_info_snapshot if self._raw_capture else None,
            raw_catalogs=self._raw_capture.catalogs if self._raw_capture else None,
            raw_var_schema=self._raw_var_schema,
        )
        if result:
            self._record_event("finalize_succeeded", {"path": str(result)})
            self._transition(
                SessionState.READY_FOR_REVIEW,
                reason="session finalized and saved successfully",
                event="finalize_succeeded",
            )
            log.info(
                "Session saved: %s (%d samples, %.0fs, laps=%s)",
                result, n_samples, duration, max_lap,
            )
            self._health.update(
                last_save_path=str(result),
                last_save_samples=n_samples,
                last_error=None,
            )
        else:
            self._record_event("finalize_failed")
            self._transition(
                SessionState.FAILED,
                reason="session finalization failed",
                event="finalize_failed",
            )
            self._health.update(last_error="Session finalization failed")
            log.error("Session finalization failed")
        self._post_finalize()

    def _build_extra_metadata(
        self, duration: float, max_lap: int | None, first: TelemetrySample,
        lap_times: dict, best_lap: float | None, lap_summary: Any,
        env: dict[str, float | None],
    ) -> dict[str, Any]:
        """Assemble the extra_metadata dict including raw-capture info."""
        meta: dict[str, Any] = {
            "duration_s": round(duration, 2),
            "lap_count": max_lap,
            "car": first.car_name,
            "dropped_samples": self._dropped_samples,
            "sample_rate_hz": self._config.sample_rate_hz,
            "lap_times": lap_times or None,
            "best_lap_time_s": best_lap,
            "total_laps": lap_summary.total_laps,
            "valid_laps": lap_summary.valid_laps,
            "clean_laps": lap_summary.clean_laps,
            "best_clean_lap_time_s": lap_summary.best_clean_lap_time_s,
            "representative_lap_number": lap_summary.representative_lap_number,
            "representative_lap_time_s": lap_summary.representative_lap_time_s,
            **env,
        }

        # Add raw-capture metadata if available.
        adapter = self._active_adapter
        if adapter is not None and adapter.supports_raw_capture():
            sdk_meta = adapter.get_sdk_metadata()
            if self._raw_capture_sim:
                meta["raw_capture_sim"] = self._raw_capture_sim
            if adapter.sim_name == "iRacing":
                iracing_cfg = self._config.iracing
                sample_mode = (
                    iracing_cfg.sample_mode
                    if isinstance(iracing_cfg, IRacingConfig)
                    else "manual"
                )
                meta["sample_mode"] = sample_mode
                meta["sdk_tick_rate_hz"] = sdk_meta.get("sdk_tick_rate_hz")
            if self._raw_capture is not None:
                observed = self._raw_capture.observed_sample_rate_hz
                meta["observed_sample_rate_hz"] = observed

        return meta

    def _post_finalize(self) -> None:
        """Cleanup after finalization and move to ready/idle path."""
        self._waiting_active_polls = 0
        self._arming_started_at = None
        self._buffer.clear()
        self._session_uid = None
        self._session_started_at = None
        self._last_raw_ts = None
        self._dropped_samples = 0
        self._latest_sample = None
        self._reset_live_state()
        self._events.clear()
        if self._raw_capture is not None:
            self._raw_capture.reset()
        self._raw_capture = None
        self._raw_capture_sim = None
        self._raw_var_schema = None

        if self._fsm.state == SessionState.READY_FOR_REVIEW and self._active_adapter is not None:
            self._health.update(sample_count=0)
            return

        if self._active_adapter is None:
            self._reset()
            return

        if self._fsm.state == SessionState.FAILED:
            self._transition(
                SessionState.IDLE,
                reason="failed session cleanup complete",
                event="failed_cleanup_complete",
            )
            self._health.update(sample_count=0)

    def _reset(self) -> None:
        self._waiting_active_polls = 0
        if self._active_adapter and self._active_adapter.connected:
            try:
                self._active_adapter.disconnect()
            except Exception:
                log.exception("Error disconnecting adapter")
        self._buffer.clear()
        self._session_uid = None
        self._session_started_at = None
        self._active_adapter = None
        self._last_raw_ts = None
        self._dropped_samples = 0
        self._latest_sample = None
        self._reset_live_state()
        self._raw_capture = None
        self._raw_capture_sim = None
        self._raw_var_schema = None
        self._monitoring = False
        self._fsm.reset()
        self._health.update(state="idle", sim=None, sample_count=0)

    # -- shutdown ----------------------------------------------------------

    def stop(self) -> None:
        """Gracefully stop: finalize any in-progress session."""
        with self._lock:
            if self._fsm.state in (SessionState.ARMING, SessionState.RECORDING):
                self._end_recording()
            elif self._fsm.state == SessionState.FINALIZING:
                self._record_event("recording_stopped", {"reason": "app_shutdown_during_finalize"})
                # Do not interrupt finalizing; allow current finalize to finish.
            elif self._fsm.state in (
                SessionState.WAITING_FOR_VALID_SESSION,
                SessionState.READY_FOR_REVIEW,
                SessionState.SIMULATOR_DETECTED,
            ):
                self._reset()
        if self._record_thread and self._record_thread.is_alive():
            self._record_thread.join(timeout=5.0)


def _positive_float(value: object) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number <= 0:
        return None
    return number


def _nonnegative_float(value: object, *, fallback: float | None = None) -> float | None:
    candidate = value if isinstance(value, (int, float)) else fallback
    if not isinstance(candidate, (int, float)):
        return None
    number = float(candidate)
    if number < 0:
        return None
    return number


def _positive_int(value: object, *, fallback: int | None = None) -> int | None:
    candidate = value if isinstance(value, int) else fallback
    if not isinstance(candidate, int):
        return None
    return candidate if candidate > 0 else None
