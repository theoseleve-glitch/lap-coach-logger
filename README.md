# Lap Coach Logger

Lap Coach Logger is a local-first Windows telemetry logger for iRacing and ACC.
It runs as a PySide6 desktop app with tray behavior, saves sessions to local
storage, and is designed to be cloned, run, packaged, installed, and used as a
personal Windows application without cloud services.

Version: `1.1.0`

## What Ships

- Native-feeling Windows desktop shell with dashboard, live view, logs, history, settings, and About dialog.
- Single-instance behavior with restore-on-second-launch.
- Start-with-Windows integration using the current-user Run key.
- PyInstaller executable build with icon and version metadata.
- Inno Setup installer with Start Menu shortcut and uninstall entry.
- Local-only storage model for config, logs, cache, runtime state, and saved sessions.

## Requirements

- Windows 10 or Windows 11
- Python 3.12 or newer for source runs and builds
- Inno Setup 6 to build the installer
- Optional: `pyirsdk` if you want iRacing shared-memory capture during source validation

## Run From Source

```powershell
cd C:\path\to\datalogger
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pip install -e .
python -m lap_coach_logger
```

Optional iRacing support during source runs:

```powershell
python -m pip install "pyirsdk>=1.3"
```

## Build The Executable

```powershell
cd C:\path\to\datalogger
.venv\Scripts\activate
build.bat
```

Verbose packaging log:

```powershell
build.bat debug
```

Result:

- `dist\LapCoachLogger\LapCoachLogger.exe`

## Build The Installer

```powershell
cd C:\path\to\datalogger
.venv\Scripts\activate
build_installer.bat
```

Full release pipeline:

```powershell
release.bat
```

Artifacts:

- `dist\LapCoachLogger\LapCoachLogger.exe`
- `LapCoachLogger-Setup-1.1.0.exe`

## Project Scripts

- `build.bat`: install packaging dependencies, run tests, build the executable
- `package.bat`: wrapper around `build.bat`
- `build_installer.bat`: compile the Inno Setup installer
- `release.bat`: build the executable and installer in sequence

## Windows Behavior

- Closing the window minimizes the app to tray.
- Choosing `Exit` from the tray menu fully shuts down the process.
- Launching the app while it is already running restores the existing window.
- Start Menu shortcuts launch with the install directory as the working directory.
- `Start with Windows` is synchronized against the current executable path.

## Local Data Layout

- Config: `%APPDATA%\LapCoachLogger\config\config.json`
- Logs: `%LOCALAPPDATA%\LapCoachLogger\logs\`
- Cache: `%LOCALAPPDATA%\LapCoachLogger\cache\`
- Runtime: `%LOCALAPPDATA%\LapCoachLogger\runtime\`
- Session output: configurable, defaulting to `Documents\LapCoachLogger_sessions`

## Branding Placeholder Layout

- `assets\icon.ico`: fallback application icon used by build and runtime
- `assets\branding\app.ico`: optional override for the main app icon
- `assets\branding\tray.ico`: optional override for the tray icon
- `assets\branding\installer.ico`: optional override for the installer icon
- `assets\branding\about-panel.txt`: placeholder About dialog art/copy

If branding overrides are missing, the build still succeeds and falls back to
the default assets.

## Reliability Notes

- Rotating logs with three backups
- Global exception logging for main thread and worker threads
- Stale temp-session cleanup on startup
- Session history ignores incomplete or partial folders
- Last saved session is surfaced in the dashboard after relaunch
- Config, log, and output folders are directly openable from the UI

## Documentation

- `CHANGELOG.md`
- `PRIVACY.md`
- `TROUBLESHOOTING.md`
- `RELEASE_CHECKLIST.md`

## Testing

```powershell
python -m pytest tests/ -q
```

## License

MIT
