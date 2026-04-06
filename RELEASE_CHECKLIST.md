# Release Checklist

## Pre-Build

- Confirm Python 3.12 or newer is installed.
- Confirm `.venv` is activated or available at the project root.
- Run `python -m pip install -r requirements.txt`.
- Install `pyirsdk` separately if iRacing validation is required.
- Confirm `assets\icon.ico` exists.

## Source Validation

- Run `python -m pytest tests/ -q` and confirm all tests pass.
- Run `python -m lap_coach_logger`.
- Confirm the dashboard opens and status reads `Idle - waiting for a simulator`.
- Confirm `Settings`, `Output`, `Logs`, and `Config` actions work.

## Packaging

- Run `build.bat`.
- Confirm `dist\LapCoachLogger\LapCoachLogger.exe` exists.
- Launch the packaged executable once directly from `dist`.
- Confirm the About dialog shows version `1.1.0` and valid config/log paths.

## Installer

- Install Inno Setup 6.
- Run `build_installer.bat`.
- Confirm the generated installer appears at the project root.
- Install to the default path.
- Launch from Start Menu and confirm the main window appears.

## Windows Behavior

- Close the window and confirm the app minimizes to tray.
- Reopen from the tray icon.
- Launch the app a second time and confirm the existing window restores.
- Enable `Start with Windows`, restart the app, and confirm the setting persists.

## Telemetry Validation

- Validate one iRacing session capture.
- Validate one ACC session capture.
- Confirm a session folder contains `metadata.json` and either `telemetry.parquet` or `telemetry.csv`.

## Uninstall

- Uninstall from Windows Apps or Control Panel.
- Confirm the Start Menu entry is removed.
- Confirm the install directory is removed.
- Confirm `%APPDATA%\LapCoachLogger` and `%LOCALAPPDATA%\LapCoachLogger` are left intact unless manually removed.