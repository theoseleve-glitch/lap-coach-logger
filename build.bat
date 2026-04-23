@echo off
REM DEV BUILD — does NOT enforce clean tree, Python pinning, or produce
REM build_info.json. For release artifacts use: scripts\build_rc1.bat
setlocal
pushd "%~dp0"

set SPEC=lap_coach_logger.spec
set PYTHON=python
set BUILD_MODE=%1

REM Activate venv if present
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat

echo.
echo === Verifying Python version ===
%PYTHON% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 (
    echo ERROR: Python 3.12 or newer is required.
    popd
    exit /b 1
)

echo.
echo === Installing / verifying build dependencies ===
%PYTHON% -m pip install -q --upgrade pip
%PYTHON% -m pip install -q -r requirements.txt

echo.
echo === Running tests ===
%PYTHON% -m pytest tests/ -q --tb=short
if errorlevel 1 (
    echo.
    echo ERROR: Tests failed — aborting build.
    popd
    exit /b 1
)

if not exist "assets\icon.ico" (
    echo.
    echo ERROR: assets\icon.ico is required for packaging.
    popd
    exit /b 1
)

echo.
echo === Building executable ===
if /I "%BUILD_MODE%"=="debug" (
    echo (debug packaging log enabled)
    %PYTHON% -m PyInstaller --noconfirm --clean --log-level DEBUG %SPEC%
) else (
    %PYTHON% -m PyInstaller --noconfirm --clean %SPEC%
)

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed.
    popd
    exit /b 1
)

echo.
echo === Build complete ===
echo Output: dist\LapCoachLogger\LapCoachLogger.exe
echo To build installer: build_installer.bat
echo.
popd
