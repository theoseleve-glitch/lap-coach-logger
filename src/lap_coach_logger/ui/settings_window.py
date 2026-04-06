"""Settings window using customtkinter.

Allows the user to edit all key configuration options:
  - Output directory (with folder picker)
  - Sample rate / interval
  - Minimum session thresholds
  - Disconnect timeout
  - Start with Windows
  - Enable iRacing / ACC
  - Debug CSV export
  - Debug logging toggle

Shows last output directory and last session summary when available.
Validates input before saving.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk

from lap_coach_logger import APP_NAME, __version__
from lap_coach_logger.utils.win_autostart import is_autostart_enabled, set_autostart

if TYPE_CHECKING:
    from lap_coach_logger.config.manager import ConfigManager
    from lap_coach_logger.config.models import AppConfig
    from lap_coach_logger.core.health import HealthMonitor

log = logging.getLogger(__name__)


class SettingsWindow:
    """Self-contained CTk settings dialog."""

    def __init__(
        self,
        config: AppConfig,
        config_manager: ConfigManager,
        health: HealthMonitor | None = None,
    ) -> None:
        self._config = config
        self._manager = config_manager
        self._health = health
        self._root: ctk.CTk | None = None
        self._thread: threading.Thread | None = None

    # -- public API --------------------------------------------------------

    def show(self) -> None:
        """Open the settings window (creates a new Tk instance each time)."""
        if self._thread and self._thread.is_alive():
            log.debug("Settings window already open")
            return
        self._thread = threading.Thread(
            target=self._build_and_run, name="settings-ui", daemon=True
        )
        self._thread.start()

    # -- internals ---------------------------------------------------------

    def _build_and_run(self) -> None:
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self._root = ctk.CTk()
        self._root.title(f"{APP_NAME} v{__version__} – Settings")
        self._root.geometry("560x620")
        self._root.resizable(False, False)

        container = ctk.CTkScrollableFrame(self._root)
        container.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Output directory ──────────────────────────────────────
        self._section(container, "Output")
        frame_dir = ctk.CTkFrame(container)
        frame_dir.pack(fill="x", padx=8, pady=4)

        self._dir_var = tk.StringVar(value=self._config.output_dir)
        ctk.CTkLabel(frame_dir, text="Session Output Folder:").pack(anchor="w", padx=8, pady=(4, 0))
        row_dir = ctk.CTkFrame(frame_dir, fg_color="transparent")
        row_dir.pack(fill="x", padx=8, pady=4)
        ctk.CTkEntry(row_dir, textvariable=self._dir_var, width=380).pack(side="left")
        ctk.CTkButton(row_dir, text="Browse…", width=80, command=self._browse).pack(
            side="left", padx=(4, 0)
        )

        # ── Sampling ──────────────────────────────────────────────
        self._section(container, "Sampling")
        self._sample_rate_var = tk.StringVar(
            value=str(round(1.0 / self._config.sample_interval_s)) if self._config.sample_interval_s > 0 else "10"
        )
        self._add_entry(container, "Sample Rate (Hz):", self._sample_rate_var)

        # ── Session Thresholds ────────────────────────────────────
        self._section(container, "Session Thresholds")
        self._min_samples_var = tk.StringVar(value=str(self._config.session.min_samples_to_save))
        self._add_entry(container, "Min Samples to Save:", self._min_samples_var)

        self._min_duration_var = tk.StringVar(value=str(self._config.session.min_duration_s))
        self._add_entry(container, "Min Duration (s):", self._min_duration_var)

        self._disconnect_timeout_var = tk.StringVar(value=str(self._config.session.data_freeze_timeout_s))
        self._add_entry(container, "Disconnect Timeout (s):", self._disconnect_timeout_var)

        # ── Sim toggles ──────────────────────────────────────────
        self._section(container, "Sims")
        self._iracing_var = tk.BooleanVar(value=self._config.iracing.enabled)
        ctk.CTkSwitch(container, text="Enable iRacing", variable=self._iracing_var).pack(
            anchor="w", padx=16, pady=2
        )
        self._acc_var = tk.BooleanVar(value=self._config.acc.enabled)
        ctk.CTkSwitch(container, text="Enable ACC", variable=self._acc_var).pack(
            anchor="w", padx=16, pady=2
        )

        # ── System ───────────────────────────────────────────────
        self._section(container, "System")
        self._autostart_var = tk.BooleanVar(value=is_autostart_enabled())
        ctk.CTkSwitch(container, text="Start with Windows", variable=self._autostart_var).pack(
            anchor="w", padx=16, pady=2
        )
        self._debug_var = tk.BooleanVar(value=self._config.debug)
        ctk.CTkSwitch(container, text="Debug logging", variable=self._debug_var).pack(
            anchor="w", padx=16, pady=2
        )
        self._debug_csv_var = tk.BooleanVar(value=self._config.writer.debug_csv_export)
        ctk.CTkSwitch(container, text="Debug CSV export (alongside Parquet)", variable=self._debug_csv_var).pack(
            anchor="w", padx=16, pady=2
        )

        # ── Status summary ───────────────────────────────────────
        if self._health:
            self._section(container, "Status")
            snap = self._health.snapshot()
            info_lines = [
                f"Current state: {snap.state}",
                f"Samples in buffer: {snap.sample_count}",
            ]
            if snap.last_save_path:
                info_lines.append(f"Last save: {snap.last_save_path}")
                info_lines.append(f"Last save samples: {snap.last_save_samples}")
            if snap.last_error:
                info_lines.append(f"Last error: {snap.last_error}")

            for line in info_lines:
                ctk.CTkLabel(container, text=line, anchor="w").pack(
                    anchor="w", padx=16, pady=1
                )

        # ── Buttons ──────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self._root, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(4, 2))
        ctk.CTkButton(btn_frame, text="Save", command=self._save).pack(side="right", padx=4)
        ctk.CTkButton(
            btn_frame, text="Cancel", fg_color="gray", command=self._close
        ).pack(side="right", padx=4)

        # ── Version footer ───────────────────────────────────────
        ctk.CTkLabel(
            self._root, text=f"v{__version__}", text_color="gray", anchor="e"
        ).pack(fill="x", padx=16, pady=(0, 6))

        self._root.protocol("WM_DELETE_WINDOW", self._close)
        self._root.mainloop()

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _section(parent: ctk.CTkFrame, title: str) -> None:
        ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=8, pady=(10, 2)
        )

    @staticmethod
    def _add_entry(parent: ctk.CTkFrame, label: str, var: tk.StringVar) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(row, text=label, width=200, anchor="w").pack(side="left")
        ctk.CTkEntry(row, textvariable=var, width=120).pack(side="left")

    def _browse(self) -> None:
        folder = filedialog.askdirectory(
            initialdir=self._dir_var.get(), title="Choose session output folder"
        )
        if folder:
            self._dir_var.set(folder)

    def _save(self) -> None:
        # ── validate ──
        errors: list[str] = []
        try:
            rate_hz = float(self._sample_rate_var.get())
            if rate_hz <= 0 or rate_hz > 100:
                # Allow > 100 Hz only if iRacing auto_sdk mode is active
                from lap_coach_logger.config.models import IRacingConfig
                is_auto_sdk = (
                    isinstance(self._config.iracing, IRacingConfig)
                    and self._config.iracing.sample_mode == "auto_sdk"
                )
                if not is_auto_sdk:
                    errors.append("Sample Rate must be between 1 and 100 Hz")
                elif rate_hz <= 0:
                    errors.append("Sample Rate must be > 0")
        except ValueError:
            errors.append("Sample Rate must be a number")
            rate_hz = 10

        try:
            min_samples = int(self._min_samples_var.get())
            if min_samples < 0:
                errors.append("Min Samples must be >= 0")
        except ValueError:
            errors.append("Min Samples must be an integer")
            min_samples = 50

        try:
            min_dur = float(self._min_duration_var.get())
            if min_dur < 0:
                errors.append("Min Duration must be >= 0")
        except ValueError:
            errors.append("Min Duration must be a number")
            min_dur = 10.0

        try:
            disc_timeout = float(self._disconnect_timeout_var.get())
            if disc_timeout <= 0:
                errors.append("Disconnect Timeout must be > 0")
        except ValueError:
            errors.append("Disconnect Timeout must be a number")
            disc_timeout = 5.0

        out_dir = self._dir_var.get().strip()
        if not out_dir:
            errors.append("Output directory must not be empty")

        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors), parent=self._root)
            return

        # ── apply ──
        self._config.output_dir = out_dir
        self._config.sample_interval_s = round(1.0 / rate_hz, 4)
        self._config.session.min_samples_to_save = min_samples
        self._config.session.min_duration_s = min_dur
        self._config.session.data_freeze_timeout_s = disc_timeout
        self._config.iracing.enabled = self._iracing_var.get()
        self._config.acc.enabled = self._acc_var.get()
        self._config.debug = self._debug_var.get()
        self._config.writer.debug_csv_export = self._debug_csv_var.get()

        # Windows autostart
        want_autostart = self._autostart_var.get()
        if want_autostart != self._config.start_with_windows:
            set_autostart(want_autostart)
            self._config.start_with_windows = want_autostart

        Path(self._config.output_dir).mkdir(parents=True, exist_ok=True)
        try:
            self._manager.save(self._config)
            log.info("Settings saved")
        except Exception:
            log.exception("Failed to save settings")
            messagebox.showerror("Error", "Failed to save settings", parent=self._root)
            return
        self._close()

    def _close(self) -> None:
        if self._root:
            self._root.destroy()
            self._root = None
