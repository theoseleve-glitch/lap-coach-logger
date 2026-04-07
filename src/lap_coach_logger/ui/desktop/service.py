"""UI service layer that bridges backend runtime objects with Qt widgets."""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import shutil
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from lap_coach_logger import __version__
from lap_coach_logger.config.manager import ConfigManager
from lap_coach_logger.config.models import AppConfig
from lap_coach_logger.core.session_coordinator import SessionCoordinator
from lap_coach_logger.core.session_review import (
    REVIEW_STATUS_IGNORED,
    REVIEW_STATUS_READY,
    load_history_entry,
    load_session_review,
    reprocess_session_bundle,
    set_session_review_status,
)
from lap_coach_logger.core.sync_queue import SyncQueueManager
from lap_coach_logger.core.sync_service import DisabledSyncService, SyncService
from lap_coach_logger.detection.process_watcher import ProcessWatcher
from lap_coach_logger.ui.desktop.session_index import SessionIndex
from lap_coach_logger.ui.desktop.status_text import build_status_detail
from lap_coach_logger.utils.paths import config_dir, logs_dir
from lap_coach_logger.utils.win_autostart import is_autostart_enabled, set_autostart

log = logging.getLogger(__name__)


def _build_sync_service(config) -> SyncService:
    """Build the appropriate sync service based on config."""
    if config.sync.enabled and config.sync.device_token:
        from lap_coach_logger.core.lap_coach_sync import LapCoachSyncService
        return LapCoachSyncService(
            api_url=config.sync.api_url,
            device_token=config.sync.device_token,
        )
    return DisabledSyncService()


_STATUS_MAP = {
    "idle": "Idle",
    "simulator_detected": "Simulator Detected",
    "waiting_for_valid_session": "Waiting",
    "arming": "Arming",
    "recording": "Recording",
    "finalizing": "Finalizing",
    "ready_for_review": "Ready for Review",
    "failed": "Failed",
}


class QtLogHandler(logging.Handler):
    """Route Python log records to a Qt signal."""

    def __init__(self, emit_line_fn, emit_event_fn, session_epoch_fn) -> None:  # noqa: ANN001
        super().__init__()
        self._emit_line_fn = emit_line_fn
        self._emit_event_fn = emit_event_fn
        self._session_epoch_fn = session_epoch_fn

    def emit(self, record: logging.LogRecord) -> None:
        try:
            ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S")
            msg = f"{ts}  {record.levelname:<8}  {record.name}  {record.getMessage()}"
            self._emit_line_fn(msg)

            event = {
                "timestamp_utc": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "time": ts,
                "severity": record.levelname,
                "module": record.name,
                "message": record.getMessage(),
                "subsystem": self._derive_subsystem(record.name),
                "simulator": self._derive_simulator(record),
                "adapter": self._derive_adapter(record),
                "created_ts": float(record.created),
                "current_session": self._is_current_session(record.created),
            }
            self._emit_event_fn(event)
        except Exception:
            return

    def _is_current_session(self, created_ts: float) -> bool:
        try:
            session_epoch = self._session_epoch_fn()
        except Exception:
            session_epoch = None
        return isinstance(session_epoch, float) and created_ts >= session_epoch

    @staticmethod
    def _derive_subsystem(logger_name: str) -> str:
        name = logger_name.lower()
        if ".adapters." in name or "process_watcher" in name:
            return "adapter"
        if "session_" in name or ".core." in name and any(
            key in name for key in ("coordinator", "session", "lap_analysis", "quality")
        ):
            return "session"
        if ".writers." in name or "finalizer" in name:
            return "storage"
        if ".ui." in name:
            return "ui"
        return "system"

    @staticmethod
    def _derive_simulator(record: logging.LogRecord) -> str:
        sim = getattr(record, "sim", None)
        if isinstance(sim, str) and sim.strip():
            return sim.strip()
        text = f"{record.name} {record.getMessage()}".lower()
        if "iracing" in text:
            return "iRacing"
        if "acc" in text or "assetto corsa competizione" in text:
            return "ACC"
        return "-"

    @staticmethod
    def _derive_adapter(record: logging.LogRecord) -> str:
        adapter = getattr(record, "adapter", None)
        if isinstance(adapter, str) and adapter.strip():
            return adapter.strip()
        text = f"{record.name} {record.getMessage()}".lower()
        if "iracingadapter" in text or "iracing_adapter" in text:
            return "IRacingAdapter"
        if "accadapter" in text or "acc_adapter" in text:
            return "ACCAdapter"
        return "-"


class DesktopService(QObject):
    """Thin service/controller for desktop shell interactions."""

    snapshot_changed = Signal(dict)
    history_changed = Signal(list)
    review_changed = Signal(dict)
    review_requested = Signal(dict)
    log_line = Signal(str)
    log_event = Signal(dict)
    settings_saved = Signal(str)
    settings_failed = Signal(str)

    def __init__(
        self,
        *,
        config: AppConfig,
        config_manager: ConfigManager,
        coordinator: SessionCoordinator,
        watcher: ProcessWatcher,
    ) -> None:
        super().__init__()
        self._config = config
        self._config_manager = config_manager
        self._coordinator = coordinator
        self._watcher = watcher
        self._latest_session: dict[str, object] | None = None
        self._last_completed_report: dict[str, object] | None = None
        self._current_review: dict[str, object] | None = None
        self._prev_state = "idle"
        self._last_snapshot_monotonic = time.monotonic()
        self._last_sample_count = 0
        self._live_update_hz = 0.0
        self._last_live_timestamp_utc: str | None = None
        self._last_live_change_monotonic: float | None = None
        self._current_session_started_epoch: float | None = None
        
        # Initialize session index for fast filtering
        self._session_index = SessionIndex(config_dir())
        self._sync_queue = SyncQueueManager(
            output_root=Path(self._config.output_dir),
            sync_enabled=self._config.sync.enabled,
            sync_service=_build_sync_service(self._config),
        )

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._emit_snapshot)

        self._history_timer = QTimer(self)
        self._history_timer.setInterval(3000)
        self._history_timer.timeout.connect(self.refresh_history)

        self._log_handler = QtLogHandler(
            self.log_line.emit,
            self.log_event.emit,
            self._get_current_session_epoch,
        )

        self._log_handler.setLevel(logging.INFO)

    # -- public accessors for config persistence ----------------------------

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def config_manager(self) -> ConfigManager:
        return self._config_manager

    # -- lifecycle -----------------------------------------------------

    def start(self) -> None:
        logging.getLogger().addHandler(self._log_handler)
        self._poll_timer.start()
        self._history_timer.start()
        self.refresh_history()
        self._emit_snapshot()

    def stop(self) -> None:
        self._poll_timer.stop()
        self._history_timer.stop()
        logging.getLogger().removeHandler(self._log_handler)

    # -- commands ------------------------------------------------------

    def start_monitoring(self) -> None:
        self._watcher.start()
        self._emit_snapshot()

    def stop_monitoring(self) -> None:
        self._coordinator.stop()
        self._watcher.stop()
        self._emit_snapshot()

    def open_output_folder(self) -> None:
        p = Path(self._config.output_dir)
        p.mkdir(parents=True, exist_ok=True)
        os.startfile(str(p))

    def open_logs_folder(self) -> None:
        os.startfile(str(logs_dir()))

    def open_config_folder(self) -> None:
        os.startfile(str(config_dir()))

    def open_path(self, path: str) -> None:
        p = Path(path)
        if p.exists():
            os.startfile(str(p))

    def save_settings(self, values: dict) -> None:
        try:
            self._config.output_dir = values["output_dir"]
            self._config.sample_interval_s = round(1.0 / float(values["sample_rate_hz"]), 4)
            self._config.session.min_duration_s = float(values["min_duration_s"])
            self._config.session.min_samples_to_save = int(values["min_samples"])
            self._config.session.data_freeze_timeout_s = float(values["disconnect_timeout_s"])
            self._config.iracing.enabled = bool(values["enable_iracing"])
            self._config.acc.enabled = bool(values["enable_acc"])
            self._config.writer.debug_csv_export = bool(values["debug_csv"])
            self._config.start_with_windows = bool(values["start_with_windows"])

            errs = self._config.validate()
            if errs:
                self.settings_failed.emit("\n".join(errs))
                return

            set_autostart(self._config.start_with_windows)
            Path(self._config.output_dir).mkdir(parents=True, exist_ok=True)
            self._sync_queue = SyncQueueManager(
                output_root=Path(self._config.output_dir),
                sync_enabled=self._config.sync.enabled,
                sync_service=_build_sync_service(self._config),
            )
            self._config_manager.save(self._config)
            self.settings_saved.emit("Settings saved")
            self._emit_snapshot()
            self.refresh_history()
        except Exception as exc:
            self.settings_failed.emit(str(exc))

    # -- snapshots -----------------------------------------------------

    def open_review(self, path: str, *, navigate: bool = False) -> dict[str, object]:
        review = load_session_review(path)
        self._current_review = review
        self.review_changed.emit(review)
        if navigate:
            self.review_requested.emit(review)
        return review

    def mark_review_ignored(self, path: str, *, ignored: bool = True) -> dict[str, object]:
        status = REVIEW_STATUS_IGNORED if ignored else REVIEW_STATUS_READY
        review = set_session_review_status(path, status)
        self._current_review = review
        self.review_changed.emit(review)
        self.refresh_history()
        return review

    def reprocess_review(self, path: str, *, navigate: bool = False) -> dict[str, object]:
        review = reprocess_session_bundle(path, config=self._config)
        self._current_review = review
        self.review_changed.emit(review)
        if navigate:
            self.review_requested.emit(review)
        self.refresh_history()
        self._last_completed_report = self._build_completed_report(review)
        self._emit_snapshot()
        return review

    def delete_review_session(self, path: str) -> None:
        target = Path(path)
        if target.exists():
            self._sync_queue.remove_bundle(target)
            shutil.rmtree(target)
        self._current_review = None
        self._last_completed_report = None
        self.refresh_history()
        self._emit_snapshot()

    def queue_session_for_sync(self, path: str) -> tuple[bool, str]:
        """Queue a saved bundle for future sync (offline-safe)."""
        target = Path(path)
        if not target.exists():
            return False, "Session folder not found"
        ok, message = self._sync_queue.queue_session(target)
        self.refresh_history()
        self._emit_snapshot()
        return ok, message

    def export_session_csv(self, session_folder: str, export_path: str) -> bool:
        """Export raw telemetry CSV from a session bundle."""
        try:
            src_folder = Path(session_folder)
            
            # Try parquet first, then CSV
            src_csv = src_folder / "telemetry.csv"
            src_parquet = src_folder / "telemetry.parquet"
            
            if src_csv.exists():
                shutil.copy2(src_csv, export_path)
                log.info(f"Exported CSV from {src_csv} to {export_path}")
                return True
            elif src_parquet.exists():
                # Convert parquet to CSV
                import pandas as pd
                df = pd.read_parquet(str(src_parquet))
                df.to_csv(export_path, index=False)
                log.info(f"Converted parquet to CSV and exported to {export_path}")
                return True
            else:
                log.warning(f"No telemetry file found in {src_folder}")
                return False
        except Exception as e:
            log.error(f"Failed to export CSV: {e}", exc_info=True)
            return False

    def get_session_folder_path(self, session_folder: str) -> str:
        """Get the local folder path for a session (for file explorer opening)."""
        return str(Path(session_folder).absolute())

    def export_support_bundle(self, export_path: str, *, current_session_only: bool = False) -> tuple[bool, str]:
        """Create privacy-safe support bundle zip for diagnostics and user support."""
        try:
            bundle_items: dict[str, str] = {}

            # App and environment metadata (safe fields only)
            app_info = {
                "app_name": "Lap Coach Logger",
                "app_version": __version__,
                "schema_version": "support_bundle_v1",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            env_info = {
                "os": {
                    "system": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "machine": platform.machine(),
                },
                "python": {
                    "version": platform.python_version(),
                    "implementation": platform.python_implementation(),
                },
                "runtime": {
                    "is_frozen": bool(getattr(sys, "frozen", False)),
                    "monitoring_active": self._watcher.is_running,
                },
                "config": {
                    "sample_interval_s": self._config.sample_interval_s,
                    "poll_interval_s": self._config.poll_interval_s,
                    "enabled_adapters": {
                        "iracing": self._config.iracing.enabled,
                        "acc": self._config.acc.enabled,
                    },
                },
            }

            bundle_items["support_bundle/app_info.json"] = json.dumps(app_info, indent=2)
            bundle_items["support_bundle/environment.json"] = json.dumps(env_info, indent=2)

            # Recent logs
            log_text = self._collect_recent_logs(current_session_only=current_session_only)
            bundle_items["support_bundle/logs/recent_app.log"] = self._sanitize_text(log_text)

            # Session artifacts (prefer current review, fallback latest session)
            session_folder = None
            if self._current_review and self._current_review.get("folder"):
                session_folder = str(self._current_review.get("folder"))
            elif self._latest_session and self._latest_session.get("folder"):
                session_folder = str(self._latest_session.get("folder"))

            if session_folder:
                sf = Path(session_folder)
                for source_name, out_name in (
                    ("session.json", "bundle_manifest.json"),
                    ("metadata.json", "session_metadata.json"),
                    ("quality_report.json", "quality_report.json"),
                ):
                    src = sf / source_name
                    if src.exists():
                        raw = src.read_text(encoding="utf-8")
                        bundle_items[f"support_bundle/session/{out_name}"] = self._sanitize_text(raw)

            manifest = {
                "bundle_type": "lap_coach_support",
                "version": 1,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "current_session_only": current_session_only,
                "included_files": sorted(bundle_items.keys()),
            }
            bundle_items["support_bundle/manifest.json"] = json.dumps(manifest, indent=2)

            self._write_zip_deterministic(Path(export_path), bundle_items)
            return True, f"Support bundle exported: {export_path}"
        except Exception as exc:
            log.error("Failed to export support bundle: %s", exc, exc_info=True)
            return False, str(exc)

    def _collect_recent_logs(self, *, current_session_only: bool) -> str:
        lines: list[str] = []
        candidates = sorted(logs_dir().glob("lap_coach_logger.log*"), key=lambda p: p.name)
        session_epoch = self._current_session_started_epoch if current_session_only else None

        for path in candidates:
            try:
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                    if session_epoch is not None and not self._line_is_current_session(line, session_epoch):
                        continue
                    lines.append(line)
            except Exception:
                continue

        # Keep only recent tail to avoid oversized support bundles
        tail = lines[-5000:]
        return "\n".join(tail)

    @staticmethod
    def _line_is_current_session(line: str, session_epoch: float) -> bool:
        # file format: "YYYY-MM-DD HH:MM:SS | LEVEL | logger | message"
        match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
        if not match:
            return False
        try:
            dt = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            return dt.timestamp() >= session_epoch
        except Exception:
            return False

    @staticmethod
    def _sanitize_text(text: str) -> str:
        sanitized = text
        home = str(Path.home())
        if home:
            sanitized = sanitized.replace(home, "<HOME>")
        username = os.environ.get("USERNAME")
        if username:
            sanitized = sanitized.replace(username, "<USER>")
        return sanitized

    @staticmethod
    def _write_zip_deterministic(path: Path, contents: dict[str, str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_STORED) as zf:
            for name in sorted(contents.keys()):
                info = zipfile.ZipInfo(filename=name, date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                zf.writestr(info, contents[name])

    def _get_current_session_epoch(self) -> float | None:
        return self._current_session_started_epoch

    @staticmethod
    def _build_completed_report(review: dict[str, object]) -> dict[str, object]:
        return {
            "samples": review.get("sample_count") or 0,
            "duration_s": review.get("duration_s") or 0,
            "laps": review.get("total_laps") or 0,
            "track": review.get("track") or "-",
            "car": review.get("car") or "-",
            "quality": review.get("quality_classification") or "-",
            "clean_laps": review.get("clean_laps") or 0,
            "best_clean_lap_time_s": review.get("best_clean_lap_time_s"),
            "sync_status": review.get("sync_status") or "not_queued",
            "sync_ready": bool(review.get("sync_ready")),
        }

    def _emit_snapshot(self) -> None:
        hs = self._coordinator.health.snapshot()
        raw_state = hs.state
        display_state = _STATUS_MAP.get(raw_state, raw_state.replace("_", " ").title())
        now_mono = time.monotonic()

        elapsed_s = 0
        if hs.session_started_at:
            try:
                started = datetime.fromisoformat(hs.session_started_at)
                elapsed_s = int((datetime.now(timezone.utc) - started).total_seconds())
                self._current_session_started_epoch = started.timestamp()
            except Exception:
                elapsed_s = 0
                self._current_session_started_epoch = None
        else:
            self._current_session_started_epoch = None

        # Detect session completion after finalize success.
        if self._prev_state == "finalizing" and raw_state == "ready_for_review":
            if hs.last_save_path:
                review = self.open_review(hs.last_save_path, navigate=True)
                self._last_completed_report = self._build_completed_report(review)
        
        self._prev_state = raw_state

        live = self._coordinator.latest_sample_snapshot()
        elapsed_since_prev = max(0.001, now_mono - self._last_snapshot_monotonic)
        sample_delta = max(0, hs.sample_count - self._last_sample_count)
        sample_rate_hz_est = sample_delta / elapsed_since_prev

        live_timestamp_utc = live.get("timestamp_utc") if isinstance(live, dict) else None
        if isinstance(live_timestamp_utc, str) and live_timestamp_utc:
            if live_timestamp_utc != self._last_live_timestamp_utc:
                if self._last_live_change_monotonic is not None:
                    dt = max(0.001, now_mono - self._last_live_change_monotonic)
                    self._live_update_hz = 1.0 / dt
                self._last_live_change_monotonic = now_mono
                self._last_live_timestamp_utc = live_timestamp_utc

        adapter = self._watcher.active_adapter
        adapter_connected = bool(adapter and adapter.connected)
        adapter_health = "connected" if adapter_connected else ("detected_disconnected" if adapter else "not_detected")
        sim_detection_status = "detected" if self._watcher.active_adapter else "not_detected"

        staleness_s: float | None = None
        if isinstance(live_timestamp_utc, str) and live_timestamp_utc:
            try:
                live_ts = datetime.fromisoformat(live_timestamp_utc)
                staleness_s = max(0.0, (datetime.now(timezone.utc) - live_ts).total_seconds())
            except Exception:
                staleness_s = None

        no_data = hs.sample_count == 0 or not live
        stale_data = staleness_s is not None and staleness_s > max(2.5, self._config.sample_interval_s * 6)
        disconnect = (raw_state in {"arming", "recording", "waiting_for_valid_session"} and not self._watcher.active_adapter) or (raw_state in {"arming", "recording"} and not adapter_connected)
        invalid_stream = (
            raw_state in {"arming", "recording"}
            and bool(live)
            and all(live.get(k) is None for k in ("speed_kph", "throttle_pct", "brake_pct", "steering_deg", "rpm"))
        )

        if disconnect:
            stream_status = "disconnect"
        elif invalid_stream:
            stream_status = "invalid_stream"
        elif stale_data:
            stream_status = "stale_data"
        elif no_data:
            stream_status = "no_data"
        else:
            stream_status = "ok"

        latest_session = self._latest_session or {}
        last_save_path = hs.last_save_path or latest_session.get("folder")
        last_save_samples = hs.last_save_samples or latest_session.get("sample_count") or 0
        payload = {
            "status": display_state,
            "raw_state": raw_state,
            "sim": hs.sim,
            "session_state": self._coordinator.state.value,
            "output_dir": self._config.output_dir,
            "sample_count": hs.sample_count,
            "elapsed_s": elapsed_s,
            "last_save_path": last_save_path,
            "last_save_samples": last_save_samples,
            "last_save_name": latest_session.get("name") if last_save_path else None,
            "last_save_ended": latest_session.get("ended") if last_save_path else None,
            "last_error": hs.last_error,
            "is_monitoring": self._watcher.is_running,
            "detected_sim": self._watcher.active_adapter.sim_name if self._watcher.active_adapter else None,
            "adapter_health": adapter_health,
            "sim_detection_status": sim_detection_status,
            "sample_rate_hz_est": round(sample_rate_hz_est, 2),
            "sample_rate_hz_config": round(1.0 / self._config.sample_interval_s, 2) if self._config.sample_interval_s > 0 else 0.0,
            "update_hz_est": round(self._live_update_hz, 2),
            "data_staleness_s": round(staleness_s, 2) if isinstance(staleness_s, float) else None,
            "stream_status": stream_status,
            "stream_flags": {
                "no_data": no_data,
                "stale_data": stale_data,
                "disconnect": disconnect,
                "invalid_stream": invalid_stream,
            },
            "status_detail": build_status_detail(
                raw_state=raw_state,
                sim=hs.sim,
                session_state=self._coordinator.state.value,
                last_error=hs.last_error,
                is_monitoring=self._watcher.is_running,
                latest_session=latest_session,
            ),
            "live": live,
            "completed_session": self._last_completed_report,
            "sync_queue_depth": self._sync_queue.queue_depth(),
            "sync_feature_enabled": self._sync_queue.sync_enabled,
        }
        self._last_snapshot_monotonic = now_mono
        self._last_sample_count = hs.sample_count
        self.snapshot_changed.emit(payload)

    def refresh_history(self) -> None:
        root = Path(self._config.output_dir)
        if not root.exists():
            self._latest_session = None
            self._session_index.clear()
            self.history_changed.emit([])
            return

        def _parse_for_index(bundle_dir: Path) -> dict[str, object]:
            # Ensure sync metadata exists before indexing/exporting history row.
            self._sync_queue.ensure_sync_metadata(bundle_dir)
            return load_history_entry(bundle_dir)

        sessions = self._session_index.sync_from_output(
            output_root=root,
            parse_entry=_parse_for_index,
            max_dirs=150,
        )

        self._latest_session = sessions[0] if sessions else None
        self.history_changed.emit(sessions)
    # -- settings values ------------------------------------------------

    def settings_snapshot(self) -> dict:
        return {
            "output_dir": self._config.output_dir,
            "sample_rate_hz": round(1.0 / self._config.sample_interval_s, 2) if self._config.sample_interval_s > 0 else 10.0,
            "min_duration_s": self._config.session.min_duration_s,
            "min_samples": self._config.session.min_samples_to_save,
            "disconnect_timeout_s": self._config.session.data_freeze_timeout_s,
            "enable_iracing": self._config.iracing.enabled,
            "enable_acc": self._config.acc.enabled,
            "start_with_windows": is_autostart_enabled(),
            "debug_csv": self._config.writer.debug_csv_export,
        }
