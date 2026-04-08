@echo off
cd /d "%~dp0"
if exist "dist\LapCoachLogger\LapCoachLogger.exe" (
    start "" "dist\LapCoachLogger\LapCoachLogger.exe"
) else (
    python -m lap_coach_logger
)
