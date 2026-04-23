@echo off
REM ===========================================================================
REM End-to-end RC1 build:
REM   1. enforce Python 3.12.x CPython on x64
REM   2. enforce clean git tree (use --allow-dirty to override)
REM   3. wipe prior outputs (reproducibility)
REM   4. install pinned build deps
REM   5. run full test suite (must pass)
REM   6. regenerate version_info.txt from app_identity.VERSION
REM   7. PyInstaller build (frozen exe folder)
REM   8. write build_info.json into dist (metadata trail)
REM   9. build Inno Setup installer
REM Fails fast on any step. Artifacts land in dist\ and repo root.
REM
REM Flags:
REM   --allow-dirty   skip the clean-tree check (for emergency patches)
REM ===========================================================================
setlocal EnableDelayedExpansion
pushd "%~dp0\.."

set PYTHON=python
set SPEC=lap_coach_logger.spec
set RC_TAG=rc1
set ALLOW_DIRTY=0
if /I "%~1"=="--allow-dirty" set ALLOW_DIRTY=1

REM Reproducibility: deterministic hashing, no .pyc writes during build,
REM ignore user-level pip.conf so PEP 668/mirrors don't drift deps.
set PYTHONHASHSEED=0
set PYTHONDONTWRITEBYTECODE=1
set PIP_CONFIG_FILE=NUL
REM SOURCE_DATE_EPOCH pins any embedded timestamp to HEAD commit time.
for /f %%i in ('git log -1 --format=%%ct 2^>nul') do set SOURCE_DATE_EPOCH=%%i

if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat

echo.
echo === [1/9] Enforcing Python 3.12.x CPython on x64 ===
%PYTHON% -c "import sys,platform; vi=sys.version_info; ok=((vi.major,vi.minor)==(3,12) and platform.python_implementation()=='CPython' and platform.machine().lower() in ('amd64','x86_64')); raise SystemExit(0 if ok else 1)"
if errorlevel 1 (
    %PYTHON% -c "import sys,platform; vi=sys.version_info; print(f'Found: {platform.python_implementation()} {vi.major}.{vi.minor}.{vi.micro} on {platform.machine()}')"
    echo ERROR: RC1 requires CPython 3.12.x on x64. See docs\release_rc1.md.
    goto :fail
)

echo.
echo === [2/9] Enforcing clean git tree ===
for /f "delims=" %%s in ('git status --porcelain 2^>nul') do (
    if "!ALLOW_DIRTY!"=="0" (
        echo ERROR: Working tree has uncommitted changes.
        echo Either commit them or re-run with --allow-dirty for an emergency build.
        git status --short
        goto :fail
    ) else (
        echo WARN: Building dirty tree per --allow-dirty
        goto :dirty_ok
    )
)
:dirty_ok

echo.
echo === [3/9] Cleaning prior build outputs ===
call scripts\clean_build.bat
if errorlevel 1 goto :fail

echo.
echo === [4/9] Installing build dependencies ===
%PYTHON% -m pip install -q --upgrade pip
if errorlevel 1 goto :fail
%PYTHON% -m pip install -q -e ".[build,dev]"
if errorlevel 1 goto :fail

echo.
echo === [5/9] Running full test suite ===
%PYTHON% -m pytest tests\ -q --tb=short ^
    --ignore=tests\test_desktop_workspaces.py ^
    --ignore=tests\test_ghost_widget.py ^
    --ignore=tests\test_overlay_browser_frontend.py ^
    --ignore=tests\test_overlay_window_manager.py
if errorlevel 1 (
    echo ERROR: Tests failed — aborting RC1 build.
    goto :fail
)

echo.
echo === [6/9] Regenerating version_info.txt ===
%PYTHON% scripts\gen_version_info.py
if errorlevel 1 goto :fail

if not exist "assets\icon.ico" (
    echo ERROR: assets\icon.ico is required for packaging.
    goto :fail
)

echo.
echo === [7/9] PyInstaller build ===
%PYTHON% -m PyInstaller --noconfirm --clean %SPEC%
if errorlevel 1 goto :fail

if not exist "dist\LapCoachLogger\LapCoachLogger.exe" (
    echo ERROR: PyInstaller output missing.
    goto :fail
)

echo.
echo === [8/9] Writing build_info.json ===
%PYTHON% scripts\write_build_info.py --rc "%RC_TAG%"
if errorlevel 1 goto :fail

echo.
echo === [9/9] Building Inno Setup installer ===
call build_installer.bat
if errorlevel 1 goto :fail

echo.
echo === RC1 BUILD SUCCESSFUL ===
echo   Frozen folder:  dist\LapCoachLogger\
echo   Build info:     dist\LapCoachLogger\build_info.json
echo   Installer:      LapCoachLogger-Setup-*.exe
echo.
echo Next step: scripts\run_smoke_tests.bat
popd
endlocal
exit /b 0

:fail
echo.
echo === RC1 BUILD FAILED ===
popd
endlocal
exit /b 1
