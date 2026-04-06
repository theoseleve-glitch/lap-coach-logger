# Privacy

Lap Coach Logger is a local-only desktop application.

## What the app does

- Reads simulator telemetry from local Windows processes and shared memory.
- Writes telemetry session files to a folder you choose on your PC.
- Writes configuration and logs to your Windows AppData folders.

## What the app does not do

- No cloud sync
- No online account
- No telemetry upload
- No analytics service
- No advertising SDK
- No background network service operated by this project

## Data locations

- Config: `%APPDATA%\LapCoachLogger\config\config.json`
- Logs: `%LOCALAPPDATA%\LapCoachLogger\logs\`
- Runtime/cache: `%LOCALAPPDATA%\LapCoachLogger\`
- Session output: your configured output folder

## Your control

- You choose the output folder.
- You can open the output, config, and log folders directly from the app.
- You can delete local data at any time after exiting the app.