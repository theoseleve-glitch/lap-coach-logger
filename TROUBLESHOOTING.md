# Troubleshooting

_Last reviewed: 2026-04-26_

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

## ACC or Assetto Corsa is running but no telemetry

ACC and Assetto Corsa expose telemetry through a Windows
shared-memory mapping that only opens once the in-game
session is loaded.

1. Confirm you are in a session (practice / quali / race),
   not the main menu.
2. Confirm the sim is enabled in Settings → Sims.
3. If you launched the sim under "Run as administrator",
   launch Lap Coach Logger as administrator too — Windows
   blocks cross-elevation access to shared memory.
4. Re-check after a sim restart; some patches change the
   shared-memory tag name and require a Lap Coach Logger
   update.

## Le Mans Ultimate is running but no telemetry

LMU also uses shared memory but ships with the rFactor 2
plugin disabled by default.

1. In LMU's `UserData/player/Settings.JSON`, ensure
   `rFactor 2 Shared Memory Map Plugin` is enabled.
2. Restart LMU.
3. Restart Lap Coach Logger.

## Overlay widgets are not visible or in the wrong place

Overlays render into transparent always-on-top windows.

1. Open the Overlay Manager (`Ctrl+5`) and confirm the
   widget toggle is on for the active layout.
2. If the widget is on but invisible, click "Auto-arrange"
   (`Ctrl+A`) — it may have been dragged off-screen on a
   previously-connected monitor.
3. If overlays don't appear in fullscreen sims, switch the
   sim to "borderless windowed" — Windows blocks always-on-
   top windows above an exclusive-fullscreen target.

## First launch shows a telemetry consent prompt

This is expected. Lap Coach Logger does not send any
crash reports or analytics until you explicitly choose Yes
on the first-run prompt (per `telemetry_consent_given`).

1. Choose Yes or No once — the choice is recorded in
   `config.json` so the prompt never re-appears.
2. You can change your choice anytime in Settings → Privacy.
3. If you chose No, no Sentry or PostHog events are sent
   for the lifetime of that consent record.

## A `config.json.v1.bak` file appeared next to my config

This is expected after a schema migration. On first launch
under a new build that bumps the config schema (T222), Lap
Coach Logger writes a byte-for-byte backup of your old
config before saving the migrated form.

1. The `.bak` file can be deleted any time after you've
   confirmed the new build works.
2. The first backup is preserved on subsequent migrations
   so the most-original state is always recoverable.

## Sessions are not syncing to the webapp

The sync feature is opt-in and requires a paired account.

1. In Settings → Sync, confirm the feature is enabled and
   you are signed in.
2. Pending uploads queue offline and dispatch when the
   network returns; check the History row for an upload
   icon vs. a pending icon.
3. If a session shows "blocked", open it once locally — the
   quality classification must be `accepted` and review
   status `approved` before a bundle is eligible to upload.

## Keyboard shortcuts do not work

Lap Coach Logger ships an extensive shortcut set (press
`F1` to see the full list).

1. Make sure the main window has focus — shortcuts are
   scoped to the app window, not global.
2. Press `F1` to verify the help overlay is showing the
   action you expect.
3. If the help and the action disagree, capture a log and
   open an issue — that's a drift bug we test for.

## High-contrast mode does not visually change the UI

The accessibility config flag (T218) ships ahead of the
visual swap. Toggling High-Contrast in Settings persists
the preference but the QML theme layer that applies it
is rolling out separately.

1. The toggle is recorded; the visual change will land in
   a follow-up build.
2. Screen-reader announcements (NVDA on Windows) for the
   primary navbar are already wired (T221).

## NVDA reads "button" with no label

QML controls that aren't `Accessible.role`-tagged are
opaque to screen readers. The primary navbar is fully
tagged; secondary surfaces (overlay manager, settings
sub-pages) are still in progress.

1. The main NavBar (Dashboard / Live / Strategy / History /
   Overlays / Settings) reads correctly.
2. If a specific button reads as "button" or as silence,
   open an issue with the page name — those are the
   surfaces still being tagged.

## Logs are empty

1. Open the Logs panel in the app.
2. Open the filesystem log directory from the top bar or About dialog.
3. Check `%LOCALAPPDATA%\LapCoachLogger\logs\lap_coach_logger.log`.

## I want a clean local reset

1. Exit the app fully from the tray.
2. Remove `%APPDATA%\LapCoachLogger\config\config.json`.
3. Optionally remove `%LOCALAPPDATA%\LapCoachLogger`.
4. Launch again to regenerate defaults.
