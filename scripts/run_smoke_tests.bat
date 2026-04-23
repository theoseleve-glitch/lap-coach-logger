@echo off
REM Launch the freshly-built exe and verify clean startup via smoke_check.py.
REM Usage: scripts\run_smoke_tests.bat
REM   0 = all smoke checks passed
REM   1 = smoke check failed (see stdout for captured log lines)
setlocal
pushd "%~dp0\.."

set PYTHON=python
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat

if not exist "dist\LapCoachLogger\LapCoachLogger.exe" (
    echo ERROR: dist\LapCoachLogger\LapCoachLogger.exe not found.
    echo Run scripts\build_rc1.bat first.
    popd
    exit /b 1
)

echo.
echo === Smoke Check 1: artifact structure ===
if not exist "dist\LapCoachLogger\build_info.json" (
    echo FAIL: build_info.json missing.
    popd
    exit /b 1
)
echo PASS: exe and build_info.json present.

echo.
echo === Smoke Check 2: runtime launch and log validation ===
%PYTHON% scripts\smoke_check.py
if errorlevel 1 (
    echo.
    echo === SMOKE TESTS FAILED ===
    popd
    exit /b 1
)

echo.
echo === ALL SMOKE TESTS PASSED ===
popd
endlocal
exit /b 0
