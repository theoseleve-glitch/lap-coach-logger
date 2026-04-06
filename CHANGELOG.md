# Changelog

All notable changes to Lap Coach Logger are documented here.

## [1.1.0] – 2026-03-22

### Added
- Full PySide6 desktop shell service architecture:
  - `Dashboard`, `Live`, `Logs`, `History` panels
  - settings dialog and About dialog
  - centralized dark theme stylesheet
- Tray menu actions for opening output/log/config folders.
- About dialog with app version, install path, config path, and log path.
- Single-instance restore signaling: second launch now asks existing instance
  to bring its window forward.
- Autostart sync helper to reconcile config intent with actual Windows Run-key state.

### Changed
- Desktop shell now uses improved user-facing status copy.
- Session history ignores incomplete `_tmp_` and partial session folders.
- Installer script hardened for Windows launch reliability:
  - explicit shortcut/run `WorkingDir={app}`
  - Start Menu folder flow retained
  - uninstall cleanup behavior tightened
- Logging setup now installs global exception hooks for main and worker threads.
- Repeatable Windows packaging scripts: `package.bat` and `release.bat`.
- Release docs: `RELEASE_CHECKLIST.md`, `TROUBLESHOOTING.md`, and `PRIVACY.md`.
- Centralized asset resolution with branding placeholder fallbacks.

### Removed
- Qt shipping path no longer requires legacy `pystray`, `Pillow`, or `customtkinter` dependencies.

### Fixed
- Process watcher now has explicit start/stop control semantics with internal
  stop event and running state.
- Session coordinator now exposes a thread-safe latest telemetry snapshot for
  live panel rendering.
- Dashboard now surfaces the most recent saved session even after relaunch.
- Desktop shell exit path now quits cleanly from tray-driven exits.
- Build and installer metadata are synchronized to version `1.1.0`.

### QA
- Test suite expanded to 56 tests.
- Full test run passes.

## [1.0.0] – 2025-01-27

### Added
- **PyInstaller build system** — `lap_coach_logger.spec` and `build.bat` produce
  a standalone `dist\LapCoachLogger\LapCoachLogger.exe`.
- **Autostart validation** — on startup the registry autostart path is checked
  and silently corrected if the exe has moved.
- **Version exposed everywhere** — tray tooltip, settings window title bar,
  settings footer, and the startup log line all show the current version.
- Noisy third-party loggers (`PIL`, `pyarrow`, `pystray`, `customtkinter`)
  are silenced at WARNING level.
- `CHANGELOG.md` and `LICENSE` files added.

### Fixed
- Duplicate `cleanup_stale_temps` static method in `SessionFinalizer` (second
  definition silently overwrote the first).
- Redundant frozen-check in `set_autostart()` replaced with `_current_exe()`.
- Version synchronized across `__init__.py` and `pyproject.toml`.

---

## [0.2.0] – 2025-01-26

### Added
- **Hardened session lifecycle** — debounce, cooldown, minimum-session filter,
  data-freeze detection, and a configurable 500 000-sample buffer cap.
- **HealthMonitor** — thread-safe status object consumed by tray and settings.
- **Full settings window** — output dir browser, sample rate, session thresholds,
  sim toggles, autostart, debug CSV toggle, and live status section.
- **Windows autostart** — registry-based `HKCU\…\Run` key management.
- **Tray enhancements** — Start / Stop Monitoring, status labels, detail
  provider, Open Sessions / Logs folder actions.
- `SessionConfig` dataclass for lifecycle thresholds.
- `WriterConfig.debug_csv_export` flag.
- `AppConfig.validate()` and `AppConfig.from_dict()` unknown-key filtering.
- 48 tests across 5 test files.

### Changed
- Session coordinator rewritten for full state-machine lifecycle with
  `WAITING_FOR_SESSION` and `COOLDOWN` states.
- Settings window rebuilt with `customtkinter` scrollable frame.

---

## [0.1.0] – 2025-01-25

### Added
- Initial project scaffold (33 files).
- `TelemetrySample` normalised schema (24 fields).
- Session state machine (7 states with explicit transition guards).
- iRacing adapter (real `pyirsdk` shared-memory integration, optional).
- ACC adapter (Windows mmap shared memory with ctypes structs).
- Process watcher (background `psutil` polling).
- `ParquetWriter` (PyArrow, Snappy compression) with CSV fallback.
- `SessionFinalizer` with temp-folder atomic rename pattern.
- System-tray icon (`pystray`) with basic context menu.
- Rotating file logger (5 MB × 3 backups).
- Graceful shutdown coordination (signals + atexit).
- 13 initial tests.
