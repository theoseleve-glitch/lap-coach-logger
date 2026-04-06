# Troubleshooting

## `No module named lap_coach_logger`

The project uses a `src` layout.

1. Activate the virtual environment.
2. Run `python -m pip install -e .`.
3. Retry `python -m lap_coach_logger`.

## The app closes but is still running

The main window minimizes to tray by design.

1. Open the Windows notification area.
2. Click the Lap Coach Logger tray icon.
3. Choose `Exit` to fully stop the app.

## `Start with Windows` does not seem to apply immediately

The setting updates the current-user Windows Run key.

1. Save settings.
2. Restart the app once.
3. Open Settings again and confirm the toggle still matches.

## Start Menu launch opens nothing visible

The running instance may already be minimized to tray.

1. Check the system tray for Lap Coach Logger.
2. Launch the app again from Start Menu.
3. The existing instance should restore instead of starting a duplicate.

## No sessions appear in History

History shows completed session folders only.

1. Confirm the selected output directory is correct.
2. Confirm the session exceeded the minimum duration and sample thresholds.
3. Open the output folder and check for `metadata.json` plus telemetry output files.

## iRacing is installed but no telemetry is captured

1. Install the optional iRacing dependency: `python -m pip install "pyirsdk>=1.3"`.
2. Confirm iRacing is enabled in Settings.
3. Start a live session, not just the launcher.

## Logs are empty

1. Open the Logs panel in the app.
2. Open the filesystem log directory from the top bar or About dialog.
3. Check `%LOCALAPPDATA%\LapCoachLogger\logs\lap_coach_logger.log`.

## I want a clean local reset

1. Exit the app fully from the tray.
2. Remove `%APPDATA%\LapCoachLogger\config\config.json`.
3. Optionally remove `%LOCALAPPDATA%\LapCoachLogger`.
4. Launch again to regenerate defaults.