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
from lap_coach_logger.config.save_scheduler import SaveScheduler
from lap_coach_logger.core.profile_store import (
    apply_profile_to_config,
    build_profile,
    load_profiles,
    match_profile,
    profile_label,
    save_profiles,
)
from lap_coach_logger.core.session_coordinator import SessionCoordinator
from lap_coach_logger.core.session_export import export_session_telemetry_csv
from lap_coach_logger.core.session_review import (
    REVIEW_STATUS_IGNORED,
    REVIEW_STATUS_READY,
    load_history_entry,
    load_session_review,
    reprocess_session_bundle,
    set_session_review_status,
)
from lap_coach_logger.core.setup_tools import (
    build_setup_diff,
    duplicate_setup_file,
    entry_map,
    install_setup_file,
    load_json_list,
    rollback_setup_operation,
    save_json_list,
    save_setup_to_bundle,
    scan_setup_library,
)
from lap_coach_logger.core.setup_coach import analyze_setup_bundle
from lap_coach_logger.core.setup_residual_model import (
    load_residual_model,
    refine_bundle_snapshot,
)
from lap_coach_logger.core.sync_queue import SyncQueueManager
from lap_coach_logger.core.sync_service import DisabledSyncService, SyncService
from lap_coach_logger.detection.process_watcher import ProcessWatcher
from lap_coach_logger.ui.desktop.session_index import SessionIndex
from lap_coach_logger.ui.desktop.status_text import build_status_detail
from lap_coach_logger.utils.file_explorer import reveal_in_file_explorer
from lap_coach_logger.utils.paths import config_dir, logs_dir
from lap_coach_logger.utils.win_autostart import is_autostart_enabled, set_autostart

log = logging.getLogger(__name__)
_SYNC_POLL_INTERVAL_MS = 15_000
_FEATURE_LIST = [
    "Live dashboard",
    "Lap recording",
    "Live coach alerts",
    "Setup file reader + diff",
    "Fuel strategy",
    "Local setup install/import",
]


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
        if "assetto corsa" in text or "assettocorsa" in text:
            return "Assetto Corsa"
        if "acc" in text or "assetto corsa competizione" in text:
            return "ACC"
        if "le mans ultimate" in text or " lmu" in text or text.endswith("lmu"):
            return "Le Mans Ultimate"
        return "-"

    @staticmethod
    def _derive_adapter(record: logging.LogRecord) -> str:
        adapter = getattr(record, "adapter", None)
        if isinstance(adapter, str) and adapter.strip():
            return adapter.strip()
        text = f"{record.name} {record.getMessage()}".lower()
        if "iracingadapter" in text or "iracing_adapter" in text:
            return "IRacingAdapter"
        if "assettocorsaadapter" in text or "assetto_corsa_adapter" in text:
            return "AssettoCorsaAdapter"
        if "accadapter" in text or "acc_adapter" in text:
            return "ACCAdapter"
        if "lmuadapter" in text or "lmu_adapter" in text:
            return "LMUAdapter"
        if "lmurecordingimport" in text:
            return "LMURecordingImport"
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
    action_message = Signal(str)
    action_failed = Signal(str)

    def __init__(
        self,
        *,
        config: AppConfig,
        config_manager: ConfigManager,
        config_saver: SaveScheduler,
        coordinator: SessionCoordinator,
        watcher: ProcessWatcher,
    ) -> None:
        super().__init__()
        self._config = config
        self._config_manager = config_manager
        self._config_saver = config_saver
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
        self._strategy_session_active = False
        self._strategy_vm = None  # set externally after construction
        self._mode_vm = None  # set externally after construction

        self._setup_favorites_path = config_dir() / "setup_favorites.json"
        self._setup_favorites = set(load_json_list(self._setup_favorites_path))
        self._setup_snapshot: dict[str, object] = {
            "status": "missing",
            "sim": "-",
            "entries": [],
            "diff_rows": [],
        }
        self._setup_selected_diff_a_id: str | None = None
        self._setup_selected_diff_b_id: str | None = None
        self._setup_last_refresh_monotonic = 0.0
        self._setup_last_sim: str | None = None
        self._setup_last_operation: dict[str, object] | None = None
        self._setup_recommendation_bundle: str | None = None
        self._setup_recommendation_snapshot: dict[str, object] = {
            "status": "no_bundle",
            "notes": ["Save a lap bundle with an embedded setup to get setup coach recommendations."],
        }
        self._profiles_path = config_dir() / "lap_pc_profiles.json"
        self._profiles = load_profiles(self._profiles_path)

        # Initialize session index for fast filtering
        self._session_index = SessionIndex(config_dir())
        self._sync_queue = self._build_sync_queue()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._emit_snapshot)

        self._history_timer = QTimer(self)
        self._history_timer.setInterval(3000)
        self._history_timer.timeout.connect(self.refresh_history)

        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(_SYNC_POLL_INTERVAL_MS)
        self._sync_timer.timeout.connect(self._process_sync_queue)

        self._log_handler = QtLogHandler(
            self.log_line.emit,
            self.log_event.emit,
            self._get_current_session_epoch,
        )

        self._log_handler.setLevel(logging.INFO)
        self._apply_runtime_mode()

    # -- public accessors for config persistence ----------------------------

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def config_manager(self) -> ConfigManager:
        return self._config_manager

    @property
    def config_saver(self) -> SaveScheduler:
        """The debounced save scheduler. Use ``request_save()`` for routine
        writes and ``flush()`` when the caller needs synchronous persistence.
        """
        return self._config_saver

    # -- lifecycle -----------------------------------------------------

    def start(self) -> None:
        logging.getLogger().addHandler(self._log_handler)
        self._poll_timer.start()
        self._history_timer.start()
        self._sync_timer.start()
        self.refresh_setup_tools()
        self.refresh_history()
        self._emit_snapshot()

    def stop(self) -> None:
        self._poll_timer.stop()
        self._history_timer.stop()
        self._sync_timer.stop()
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
        # T068: cross-platform reveal-in-file-manager (Windows
        # Explorer / macOS Finder / Linux xdg-open). Auto-creates
        # the output dir on demand because users expect this even
        # before the first session is captured.
        p = Path(self._config.output_dir)
        p.mkdir(parents=True, exist_ok=True)
        reveal_in_file_explorer(p)

    def open_logs_folder(self) -> None:
        reveal_in_file_explorer(logs_dir())

    def open_config_folder(self) -> None:
        reveal_in_file_explorer(config_dir())

    def open_path(self, path: str) -> None:
        # No mkdir here: open_path is for revealing an EXISTING
        # session bundle; missing-path is a true no-op.
        reveal_in_file_explorer(path)

    def refresh_setup_tools(self) -> None:
        self._refresh_setup_state(force=True)
        self._emit_snapshot()

    def refresh_operations(self) -> None:
        self._profiles = load_profiles(self._profiles_path)
        self._emit_snapshot()

    def save_operations_profile(self, name: str, scope: str) -> None:
        live = self._coordinator.latest_sample_snapshot()
        sim = str(self._coordinator.health.snapshot().sim or live.get("sim") or "").strip() or None
        car = str(live.get("car_name") or "").strip() or None
        driver = self._config.driver_name.strip() or None
        profile = build_profile(
            name=name,
            scope=scope,
            config=self._config,
            sim=sim,
            car=car,
            driver=driver,
        )
        self._profiles.append(profile)
        save_profiles(self._profiles_path, self._profiles)
        self._emit_snapshot()
        self.action_message.emit(f"Saved {profile.get('name')} profile")

    def apply_operations_profile(self, profile_id: str | None) -> None:
        profile = next((item for item in self._profiles if str(item.get("id") or "") == str(profile_id or "")), None)
        if profile is None:
            self.action_failed.emit("Select a profile first.")
            return
        try:
            apply_profile_to_config(profile, self._config)
            errs = self._config.validate()
            if errs:
                self.action_failed.emit("\n".join(errs))
                return
            set_autostart(self._config.start_with_windows)
            self._watcher.set_poll_interval(self._config.poll_interval_s)
            self._sync_queue = self._build_sync_queue()
            self._apply_runtime_mode()
            self._config_manager.save(self._config)
            self._emit_snapshot()
            self.action_message.emit(f"Applied {profile.get('name')} profile")
        except Exception as exc:
            self.action_failed.emit(str(exc))

    def toggle_active_raw_capture(self) -> None:
        sim_name = str(self._coordinator.health.snapshot().sim or "").strip()
        if not sim_name:
            self.action_failed.emit("No active simulator is available for raw recorder control.")
            return
        message = None
        if sim_name == "iRacing":
            self._config.iracing.raw_capture_enabled = not self._config.iracing.raw_capture_enabled
            message = f"iRacing raw recorder {'enabled' if self._config.iracing.raw_capture_enabled else 'disabled'}"
        elif sim_name == "Assetto Corsa":
            self._config.assetto_corsa.raw_capture_enabled = not self._config.assetto_corsa.raw_capture_enabled
            message = f"Assetto Corsa raw recorder {'enabled' if self._config.assetto_corsa.raw_capture_enabled else 'disabled'}"
        elif sim_name == "ACC":
            self._config.acc.raw_capture_enabled = not self._config.acc.raw_capture_enabled
            message = f"ACC raw recorder {'enabled' if self._config.acc.raw_capture_enabled else 'disabled'}"
        elif sim_name == "Le Mans Ultimate":
            self._config.lmu.raw_capture_enabled = not self._config.lmu.raw_capture_enabled
            message = f"Le Mans Ultimate raw recorder {'enabled' if self._config.lmu.raw_capture_enabled else 'disabled'}"
        if message is None:
            self.action_failed.emit("Raw recorder control is unavailable for the active simulator.")
            return
        try:
            self._config_manager.save(self._config)
        except Exception as exc:
            self.action_failed.emit(str(exc))
            return
        self._emit_snapshot()
        self.action_message.emit(message)

    def select_setup_diff(self, setup_a_id: str | None, setup_b_id: str | None) -> None:
        self._setup_selected_diff_a_id = setup_a_id or None
        self._setup_selected_diff_b_id = setup_b_id or None
        self._refresh_setup_state(force=True)
        self._emit_snapshot()

    def toggle_setup_favorite(self, setup_id: str | None) -> None:
        if not setup_id:
            self.action_failed.emit("Select a setup first.")
            return
        if setup_id in self._setup_favorites:
            self._setup_favorites.remove(setup_id)
            message = "Setup removed from favorites"
        else:
            self._setup_favorites.add(setup_id)
            message = "Setup added to favorites"
        save_json_list(self._setup_favorites_path, self._setup_favorites)
        self._refresh_setup_state(force=True)
        self._emit_snapshot()
        self.action_message.emit(message)

    def install_setup_from_file(self, source_path: str, target_setup_id: str | None = None) -> None:
        source = Path(source_path)
        if not source.exists():
            self.action_failed.emit("Selected setup file was not found.")
            return

        target_entry = self._resolve_setup_entry(target_setup_id) or self._resolve_setup_entry(
            str(self._setup_snapshot.get("current_setup_id") or "")
        )
        destination_dir = None
        if target_entry is not None:
            destination_dir = Path(str(target_entry.get("path"))).parent
        else:
            root = self._setup_snapshot.get("root")
            if isinstance(root, str) and root:
                destination_dir = Path(root)
        if destination_dir is None:
            self.action_failed.emit("No native setup folder is available for install.")
            return

        try:
            installed_path, operation = install_setup_file(source, destination_dir)
        except Exception as exc:
            self.action_failed.emit(f"Setup install failed: {exc}")
            return

        self._setup_last_operation = operation
        self._refresh_setup_state(force=True)
        self._emit_snapshot()
        self.action_message.emit(f"Installed {installed_path.name}")

    def duplicate_setup(self, setup_id: str | None, new_name: str) -> None:
        source_entry = self._resolve_setup_entry(setup_id) or self._resolve_setup_entry(
            str(self._setup_snapshot.get("current_setup_id") or "")
        )
        if source_entry is None:
            self.action_failed.emit("Select a setup to duplicate.")
            return

        source_path = Path(str(source_entry.get("path")))
        duplicate_name = new_name.strip() or f"{source_path.stem}_copy"
        try:
            duplicated_path, operation = duplicate_setup_file(source_path, duplicate_name)
        except Exception as exc:
            self.action_failed.emit(f"Setup duplicate failed: {exc}")
            return

        self._setup_last_operation = operation
        self._refresh_setup_state(force=True)
        self._setup_selected_diff_b_id = str(duplicated_path.resolve())
        self._emit_snapshot()
        self.action_message.emit(f"Duplicated setup as {duplicated_path.name}")

    def rollback_setup_change(self) -> None:
        try:
            message = rollback_setup_operation(self._setup_last_operation)
        except Exception as exc:
            self.action_failed.emit(str(exc))
            return

        self._setup_last_operation = None
        self._refresh_setup_state(force=True)
        self._emit_snapshot()
        self.action_message.emit(message)

    def save_setup_with_last_session(self, setup_id: str | None) -> None:
        source_entry = self._resolve_setup_entry(setup_id) or self._resolve_setup_entry(
            str(self._setup_snapshot.get("current_setup_id") or "")
        )
        if source_entry is None:
            self.action_failed.emit("Select a setup to bundle with a lap first.")
            return

        bundle_root = None
        if self._current_review and self._current_review.get("folder"):
            bundle_root = Path(str(self._current_review["folder"]))
        elif self._latest_session and self._latest_session.get("folder"):
            bundle_root = Path(str(self._latest_session["folder"]))
        else:
            health = self._coordinator.health.snapshot()
            if health.last_save_path:
                bundle_root = Path(health.last_save_path)
        if bundle_root is None or not bundle_root.exists():
            self.action_failed.emit("No saved lap bundle is available yet.")
            return

        try:
            saved_path = save_setup_to_bundle(Path(str(source_entry.get("path"))), bundle_root)
        except Exception as exc:
            self.action_failed.emit(f"Setup bundle save failed: {exc}")
            return

        self._setup_recommendation_bundle = None
        self._refresh_setup_state(force=True)
        self._emit_snapshot()
        self.action_message.emit(f"Saved setup into {saved_path.parent.name}")

    def _build_sync_queue(self) -> SyncQueueManager:
        return SyncQueueManager(
            output_root=Path(self._config.output_dir),
            sync_enabled=self._config.sync.enabled,
            sync_service=_build_sync_service(self._config),
        )

    def _refresh_setup_state(
        self,
        *,
        force: bool = False,
        current_sim: str | None = None,
        live: dict[str, object] | None = None,
    ) -> None:
        now = time.monotonic()
        if (
            not force
            and self._setup_snapshot
            and current_sim == self._setup_last_sim
            and now - self._setup_last_refresh_monotonic < 5.0
        ):
            return

        snapshot = scan_setup_library(
            sim_preference=current_sim,
            live=live,
            favorites=self._setup_favorites,
        )
        entries = entry_map(snapshot.get("entries") or [])
        if self._setup_selected_diff_a_id not in entries:
            self._setup_selected_diff_a_id = str(snapshot.get("diff_default_a_id") or "") or None
        if self._setup_selected_diff_b_id not in entries:
            self._setup_selected_diff_b_id = str(snapshot.get("diff_default_b_id") or "") or None

        diff_rows = build_setup_diff(
            entries.get(self._setup_selected_diff_a_id or ""),
            entries.get(self._setup_selected_diff_b_id or ""),
        )
        snapshot["recommendation"] = self._build_setup_recommendation_snapshot()
        snapshot["selected_diff_a_id"] = self._setup_selected_diff_a_id
        snapshot["selected_diff_b_id"] = self._setup_selected_diff_b_id
        snapshot["diff_rows"] = diff_rows[:160]
        snapshot["rollback_available"] = self._setup_last_operation is not None
        self._setup_snapshot = snapshot
        self._setup_last_refresh_monotonic = now
        self._setup_last_sim = current_sim

    def _resolve_setup_entry(self, setup_id: str | None) -> dict[str, object] | None:
        if not setup_id:
            return None
        entries = entry_map(self._setup_snapshot.get("entries") or [])
        return entries.get(setup_id)

    def _build_setup_recommendation_snapshot(self) -> dict[str, object]:
        bundle_dir: str | None = None
        if self._current_review and self._current_review.get("folder"):
            bundle_dir = str(self._current_review.get("folder"))
        elif self._latest_session and self._latest_session.get("folder"):
            bundle_dir = str(self._latest_session.get("folder"))

        if not bundle_dir:
            self._setup_recommendation_bundle = None
            self._setup_recommendation_snapshot = {
                "status": "no_bundle",
                "notes": ["Save a lap bundle with an embedded setup to get setup coach recommendations."],
            }
            return self._setup_recommendation_snapshot

        if bundle_dir == self._setup_recommendation_bundle:
            return self._setup_recommendation_snapshot

        try:
            analysis = analyze_setup_bundle(bundle_dir)
            snapshot = analysis.to_dict()
            model_path = config_dir() / "setup_coach_residual_model.json"
            if model_path.exists():
                model = load_residual_model(model_path)
                refined, adjustments = refine_bundle_snapshot(
                    analysis,
                    bundle_dir,
                    model,
                )
                snapshot = refined.to_dict()
                if adjustments:
                    snapshot["ml_adjustments"] = [adjustment.to_dict() for adjustment in adjustments]
            snapshot["bundle_name"] = Path(bundle_dir).name
        except Exception as exc:
            snapshot = {
                "status": "failed",
                "bundle_name": Path(bundle_dir).name,
                "notes": [f"Setup coach analysis failed: {exc}"],
            }
        self._setup_recommendation_bundle = bundle_dir
        self._setup_recommendation_snapshot = snapshot
        return snapshot

    def save_settings(self, values: dict) -> None:
        try:
            self._config.output_dir = values["output_dir"]
            self._config.driver_name = str(values["driver_name"]).strip()
            self._config.sample_interval_s = round(1.0 / float(values["sample_rate_hz"]), 4)
            self._config.poll_interval_s = float(values["poll_interval_s"])
            self._config.session.min_duration_s = float(values["min_duration_s"])
            self._config.session.min_samples_to_save = int(values["min_samples"])
            self._config.session.data_freeze_timeout_s = float(values["disconnect_timeout_s"])
            self._config.session_end_grace_s = float(values["session_end_grace_s"])
            self._config.iracing.enabled = bool(values["enable_iracing"])
            self._config.assetto_corsa.enabled = bool(values["enable_assetto_corsa"])
            self._config.assetto_corsa.raw_capture_enabled = bool(values["assetto_corsa_raw_capture_enabled"])
            self._config.acc.enabled = bool(values["enable_acc"])
            self._config.acc.raw_capture_enabled = bool(values["acc_raw_capture_enabled"])
            self._config.lmu.enabled = bool(values["enable_lmu"])
            self._config.lmu.raw_capture_enabled = bool(values["lmu_raw_capture_enabled"])
            self._config.iracing.sample_mode = str(values["iracing_sample_mode"])
            self._config.iracing.raw_capture_enabled = bool(values["iracing_raw_capture_enabled"])
            self._config.overlay.enabled = bool(values["overlay_enabled"])
            self._config.overlay.refresh_rate_hz = int(values["overlay_refresh_rate_hz"])
            self._config.overlay.opacity = float(values["overlay_opacity"])
            self._config.overlay.pin_mode = str(values["overlay_pin_mode"])
            self._config.sync.enabled = bool(values["sync_enabled"])
            self._config.sync.api_url = str(values["sync_api_url"]).strip()
            self._config.sync.device_token = str(values["sync_device_token"]).strip()
            self._config.writer.debug_csv_export = bool(values["debug_csv"])
            self._config.start_with_windows = bool(values["start_with_windows"])
            self._config.low_resource_mode = bool(values["low_resource_mode"])
            # T065: master opt-out — bootstrap re-reads this next launch.
            self._config.telemetry_enabled = bool(
                values.get("telemetry_enabled", True)
            )

            errs = self._config.validate()
            if errs:
                self.settings_failed.emit("\n".join(errs))
                return

            set_autostart(self._config.start_with_windows)
            Path(self._config.output_dir).mkdir(parents=True, exist_ok=True)
            self._watcher.set_poll_interval(self._config.poll_interval_s)
            self._sync_queue = self._build_sync_queue()
            self._apply_runtime_mode()
            # Explicit Save button: write synchronously so the "Saved"
            # toast only appears after the bytes hit disk, and any I/O
            # error surfaces via the outer except -> settings_failed.
            self._config_manager.save(self._config)
            self._config_saver.flush_now()
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
        if self._current_review and Path(str(self._current_review.get("folder") or "")) == target:
            self._current_review = load_session_review(target)
            self.review_changed.emit(self._current_review)
        if ok and self._sync_queue.sync_enabled:
            self._process_sync_queue()
        self.refresh_history()
        self._emit_snapshot()
        return ok, message

    def export_session_csv(self, session_folder: str, export_path: str) -> bool:
        """Export raw telemetry CSV from a session bundle."""
        try:
            return export_session_telemetry_csv(session_folder, export_path)
        except Exception as exc:
            log.error("Failed to export CSV: %s", exc, exc_info=True)
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
                        "assetto_corsa": self._config.assetto_corsa.enabled,
                        "acc": self._config.acc.enabled,
                        "lmu": self._config.lmu.enabled,
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

    def _process_sync_queue(self) -> None:
        results = self._sync_queue.process_queue(max_items=3)
        if not results:
            return

        synced = sum(1 for result in results if result.get("status") == "synced")
        failed = sum(1 for result in results if result.get("status") == "failed")
        dropped = sum(1 for result in results if result.get("status") == "dropped_missing_bundle")
        log.info(
            "Processed sync queue: %d synced, %d failed, %d dropped",
            synced,
            failed,
            dropped,
        )

        self.refresh_history()

        if self._current_review and self._current_review.get("folder"):
            try:
                self._current_review = load_session_review(str(self._current_review["folder"]))
            except Exception:
                log.debug("Could not refresh current review after sync processing", exc_info=True)
            else:
                self.review_changed.emit(self._current_review)

        self._emit_snapshot()

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
        self._refresh_setup_state(current_sim=hs.sim, live=live)
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
        live_coaching = self._coordinator.live_coaching_snapshot()
        hardware_diagnostics = self._coordinator.hardware_diagnostics_snapshot()
        platform_analysis = self._coordinator.platform_analysis_snapshot()
        operations = self._build_operations_snapshot(
            live=live if isinstance(live, dict) else {},
            active_sim=hs.sim,
            monitoring=bool(self._watcher.is_running),
        )
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
            # Relative/gap data (gap timing widget). None when sim doesn't expose it.
            "relative": self._coordinator.latest_relative_snapshot(),
            "live_coaching": live_coaching,
            "hardware_diagnostics": hardware_diagnostics,
            "platform_analysis": platform_analysis,
            "operations": operations,
            "setup_tools": self._setup_snapshot,
            "completed_session": self._last_completed_report,
            "sync_queue_depth": self._sync_queue.queue_depth(),
            "sync_feature_enabled": self._sync_queue.sync_enabled,
        }
        # Strategy auto-capture lifecycle
        if self._strategy_vm is not None:
            if raw_state in ("arming", "recording") and not self._strategy_session_active:
                self._strategy_session_active = True
                live = payload.get("live", {})
                session_type = str(live.get("session_type") or "practice")
                track = str(live.get("track_name") or "")
                car = str(live.get("car_name") or "")
                if track and car:
                    self._strategy_vm.on_session_detected(session_type, track, car)
                if self._mode_vm is not None:
                    self._mode_vm.onSessionDetected(session_type, 0.0, False)
            elif raw_state in ("idle",) and self._strategy_session_active:
                self._strategy_session_active = False
                self._strategy_vm.on_session_ended()

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
            max_dirs=None,
        )

        self._latest_session = sessions[0] if sessions else None
        self.history_changed.emit(sessions)

    def overlay_snapshot(self) -> dict[str, object]:
        hs = self._coordinator.health.snapshot()
        return {
            "status": _STATUS_MAP.get(hs.state, hs.state.replace("_", " ").title()),
            "is_monitoring": self._watcher.is_running,
            "sim": hs.sim,
            "live": self._coordinator.latest_sample_snapshot(),
            "live_coaching": self._coordinator.live_coaching_snapshot(),
            "hardware_diagnostics": self._coordinator.hardware_diagnostics_snapshot(),
            "platform_analysis": self._coordinator.platform_analysis_snapshot(),
            "setup_tools": self._setup_snapshot,
        }

    # -- settings values ------------------------------------------------

    def _apply_runtime_mode(self) -> None:
        if self._config.low_resource_mode:
            self._poll_timer.setInterval(900)
            self._history_timer.setInterval(6000)
        else:
            self._poll_timer.setInterval(500)
            self._history_timer.setInterval(3000)

    def _build_operations_snapshot(
        self,
        *,
        live: dict[str, object],
        active_sim: str | None,
        monitoring: bool,
    ) -> dict[str, object]:
        sim = str(active_sim or live.get("sim") or "").strip()
        car = str(live.get("car_name") or "").strip()
        driver = self._config.driver_name.strip()
        matched_profile = match_profile(self._profiles, sim=sim, car=car, driver=driver)
        enabled_sims = [
            label
            for enabled, label in (
                (self._config.iracing.enabled, "iRacing"),
                (self._config.assetto_corsa.enabled, "Assetto Corsa"),
                (self._config.acc.enabled, "ACC"),
                (self._config.lmu.enabled, "Le Mans Ultimate"),
            )
            if enabled
        ]
        raw_status = "Unavailable"
        if sim == "iRacing":
            raw_status = "Armed" if self._config.iracing.raw_capture_enabled else "Off"
        elif sim == "Assetto Corsa":
            raw_status = "Armed" if self._config.assetto_corsa.raw_capture_enabled else "Off"
        elif sim == "ACC":
            raw_status = "Armed" if self._config.acc.raw_capture_enabled else "Off"
        elif sim == "Le Mans Ultimate":
            raw_status = "Armed" if self._config.lmu.raw_capture_enabled else "Off"
        safe_update = "Manual only"
        safe_update_detail = "Auto-update is unavailable in this dev build."
        if getattr(sys, "frozen", False):
            safe_update = "Packaged build"
            safe_update_detail = "Use signed installer updates; no live patching while recording."
        profiles = [
            {
                "id": str(profile.get("id") or ""),
                "label": profile_label(profile),
                "name": str(profile.get("name") or "Profile"),
                "scope": str(profile.get("scope") or "sim"),
                "matched": bool(matched_profile and str(matched_profile.get("id") or "") == str(profile.get("id") or "")),
            }
            for profile in self._profiles
        ]
        return {
            "rows": {
                "autodetect": {
                    "label": "Watching" if monitoring else "Paused",
                    "detail": "Enabled sims: " + (", ".join(enabled_sims) if enabled_sims else "none"),
                },
                "auto_start": {
                    "label": "Armed" if monitoring else "Stopped",
                    "detail": "Sessions auto-arm when a supported sim becomes active.",
                },
                "pin_mode": {
                    "label": {
                        "overlay_on_top": "Overlay on top",
                        "dashboard_on_top": "Main window on top",
                        "floating": "Floating windows",
                    }.get(self._config.overlay.pin_mode, "Overlay on top"),
                    "detail": "Overlay and main window pinning follow the current runtime mode.",
                },
                "profiles": {
                    "label": str(matched_profile.get("name") or "No active profile") if matched_profile else "No active profile",
                    "detail": f"Context: {sim or '-'} / {car or '-'} / {driver or '-'}",
                },
                "safe_update": {
                    "label": safe_update,
                    "detail": safe_update_detail,
                },
                "crash_recovery": {
                    "label": "Enabled",
                    "detail": "Stale temp sessions are cleaned on startup and saved bundles are preserved.",
                },
                "low_resource": {
                    "label": "Enabled" if self._config.low_resource_mode else "Disabled",
                    "detail": "Reduces dashboard polling and caps overlay cost for weaker systems.",
                },
                "raw_recorder": {
                    "label": raw_status,
                    "detail": f"Raw telemetry recorder for debugging is scoped to {sim or 'the active sim'}.",
                },
            },
            "profiles": profiles,
            "feature_list": list(_FEATURE_LIST),
            "context": {
                "sim": sim or "-",
                "car": car or "-",
                "driver": driver or "-",
            },
        }

    def settings_snapshot(self) -> dict:
        return {
            "output_dir": self._config.output_dir,
            "driver_name": self._config.driver_name,
            "sample_rate_hz": round(1.0 / self._config.sample_interval_s, 2) if self._config.sample_interval_s > 0 else 10.0,
            "poll_interval_s": self._config.poll_interval_s,
            "min_duration_s": self._config.session.min_duration_s,
            "min_samples": self._config.session.min_samples_to_save,
            "disconnect_timeout_s": self._config.session.data_freeze_timeout_s,
            "session_end_grace_s": self._config.session_end_grace_s,
            "enable_iracing": self._config.iracing.enabled,
            "enable_assetto_corsa": self._config.assetto_corsa.enabled,
            "assetto_corsa_raw_capture_enabled": self._config.assetto_corsa.raw_capture_enabled,
            "enable_acc": self._config.acc.enabled,
            "acc_raw_capture_enabled": self._config.acc.raw_capture_enabled,
            "enable_lmu": self._config.lmu.enabled,
            "lmu_raw_capture_enabled": self._config.lmu.raw_capture_enabled,
            "iracing_sample_mode": self._config.iracing.sample_mode,
            "iracing_raw_capture_enabled": self._config.iracing.raw_capture_enabled,
            "start_with_windows": is_autostart_enabled(),
            "low_resource_mode": self._config.low_resource_mode,
            "overlay_enabled": self._config.overlay.enabled,
            "overlay_refresh_rate_hz": self._config.overlay.refresh_rate_hz,
            "overlay_opacity": self._config.overlay.opacity,
            "overlay_pin_mode": self._config.overlay.pin_mode,
            "sync_enabled": self._config.sync.enabled,
            "sync_api_url": self._config.sync.api_url,
            "sync_device_token": self._config.sync.device_token,
            "debug_csv": self._config.writer.debug_csv_export,
            "telemetry_enabled": self._config.telemetry_enabled,
        }
