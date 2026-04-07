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
from lap_coach_logger.config.models import AppConfig, IRacingConfig
from lap_coach_logger.core.health import HealthMonitor
from lap_coach_logger.core.iracing_raw_capture import IRacingRawCapture
from lap_coach_logger.core.lap_analysis import classify_laps
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.session_state import SessionState, SessionStateMachine
from lap_coach_logger.utils.shutdown import shutdown_requested
from lap_coach_logger.writers.bundle_schema import LapRecord, SessionEvent
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
        self._events: list[SessionEvent] = []
        self._record_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._monitoring = False
        self._waiting_active_polls: int = 0
        self._arming_started_at: float | None = None

        # Data-freeze tracking
        self._last_raw_ts: float | None = None
        self._last_raw_ts_changed_at: float = 0.0

        # iRacing raw capture state
        self._raw_capture: IRacingRawCapture | None = None
        self._iracing_var_schema: list[dict[str, Any]] | None = None

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

    def latest_sample_snapshot(self) -> dict[str, object]:
        """Return a shallow dict snapshot of the latest sample for UI display."""
        with self._lock:
            if self._latest_sample is None:
                return {}
            d = self._latest_sample.to_dict()
        return {
            "timestamp_utc": d.get("timestamp_utc"),
            "raw_source_timestamp": d.get("raw_source_timestamp"),
            "sim": d.get("sim"),
            "track_name": d.get("track_name"),
            "car_name": d.get("car_name"),
            "session_type": d.get("session_type"),
            "speed_kph": d.get("speed_kph"),
            "rpm": d.get("rpm"),
            "gear": d.get("gear"),
            "throttle_pct": d.get("throttle_pct"),
            "brake_pct": d.get("brake_pct"),
            "steering_deg": d.get("steering_deg"),
            "clutch_pct": d.get("clutch_pct"),
            "lap_number": d.get("lap_number"),
            "lap_distance_m": d.get("lap_distance_m"),
            "session_time_s": d.get("session_time_s"),
            "is_on_track": d.get("is_on_track"),
            "is_in_pits": d.get("is_in_pits"),
            "fuel_level": d.get("fuel_level"),
            "lat_accel_g": d.get("lat_accel_g"),
            "long_accel_g": d.get("long_accel_g"),
            "lap_dist_pct": d.get("lap_dist_pct"),
            "track_length_m": d.get("track_length_m"),
            # Orientation
            "yaw_deg": d.get("yaw_deg"),
            "pitch_deg": d.get("pitch"),
            "roll_deg": d.get("roll"),
            # Tyre temperatures
            "tyre_temp_lf": d.get("tyre_temp_lf"),
            "tyre_temp_rf": d.get("tyre_temp_rf"),
            "tyre_temp_lr": d.get("tyre_temp_lr"),
            "tyre_temp_rr": d.get("tyre_temp_rr"),
            # Brake temperatures
            "brake_temp_lf": d.get("brake_temp_lf"),
            "brake_temp_rf": d.get("brake_temp_rf"),
            "brake_temp_lr": d.get("brake_temp_lr"),
            "brake_temp_rr": d.get("brake_temp_rr"),
            # World position
            "world_pos_x": d.get("world_pos_x"),
            "world_pos_y": d.get("world_pos_y"),
            "world_pos_z": d.get("world_pos_z"),
            # Race position
            "position": d.get("position"),
            "num_cars": d.get("num_cars"),
            # Environment
            "track_temp_c": d.get("track_temp_c"),
            "air_temp_c": d.get("air_temp_c"),
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
            use_tick_driven
            and isinstance(self._config.iracing, IRacingConfig)
            and self._config.iracing.raw_capture_enabled
        )

        if use_tick_driven:
            log.info("iRacing auto_sdk mode: tick-driven sampling enabled")
        if use_raw_capture:
            log.info("iRacing raw capture enabled")

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
                                self._init_raw_capture()
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
                        self._record_event("recording_started")
                        self._transition(
                            SessionState.RECORDING,
                            reason="first valid telemetry sample received",
                            event="recording_started",
                        )
                        self._append_sample(sample)
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
                        self._append_sample(sample)

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
        if self._raw_capture is not None:
            self._raw_capture.reset()
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

    def _append_sample(self, sample: TelemetrySample) -> None:
        """Append sample with buffer cap protection."""
        self._latest_sample = sample
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

    # -- iRacing raw capture helpers ----------------------------------------

    def _init_raw_capture(self) -> None:
        """Set up the raw capture helper and load catalogs."""
        rc = IRacingRawCapture()
        iracing_cfg = self._config.iracing
        if isinstance(iracing_cfg, IRacingConfig):
            rc.load_catalogs(
                localserver_track_fields_path=iracing_cfg.catalog_localserver_track_fields,
                localserver_arq_messages_path=iracing_cfg.catalog_localserver_arq_messages,
                sim_param_names_path=iracing_cfg.catalog_sim_param_names,
            )
            # Cache the live var schema for channel metadata
            self._load_iracing_var_schema(iracing_cfg.catalog_live_var_schema)
        self._raw_capture = rc
        log.info("iRacing raw capture initialized")

    def _load_iracing_var_schema(self, path: str) -> None:
        """Load the live var schema JSON for channel metadata."""
        import json
        from pathlib import Path

        default = Path(r"C:\Users\Admin\Documents\Telemetry\Analysis\V2_claude_ai\artifacts\iracing_live_var_schema.json")
        p = Path(path) if path else default
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    self._iracing_var_schema = json.load(f)
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
            iracing_raw_samples=self._raw_capture.raw_buffer if self._raw_capture else None,
            iracing_raw_columns=self._raw_capture.get_raw_column_names() if self._raw_capture else None,
            iracing_session_info=self._raw_capture.session_info_snapshot if self._raw_capture else None,
            iracing_catalogs=self._raw_capture.catalogs if self._raw_capture else None,
            iracing_var_schema=self._iracing_var_schema,
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
        """Assemble the extra_metadata dict including iRacing sampling info."""
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

        # Add iRacing sampling metadata if available
        adapter = self._active_adapter
        if adapter is not None and adapter.supports_raw_capture():
            sdk_meta = adapter.get_sdk_metadata()
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
        self._events.clear()
        if self._raw_capture is not None:
            self._raw_capture.reset()

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
