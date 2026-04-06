@echo off
REM Build Windows installer with Inno Setup (ISCC.exe must be installed)
setlocal EnableDelayedExpansion
pushd "%~dp0"

set ISS=installer\LapCoachLogger.iss
set PYTHON=python
set ISCC=
set INSTALLER_ICON=..\assets\icon.ico
set ISCC_PROGRAMFILES=%ProgramFiles%\Inno Setup 6\ISCC.exe
set ISCC_PROGRAMFILES_X86=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
set ISCC_LOCALAPPDATA=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe

if exist "%ISCC_PROGRAMFILES%" set ISCC="%ISCC_PROGRAMFILES%"
if not defined ISCC if exist "%ISCC_PROGRAMFILES_X86%" set ISCC="%ISCC_PROGRAMFILES_X86%"
if not defined ISCC if exist "%ISCC_LOCALAPPDATA%" set ISCC="%ISCC_LOCALAPPDATA%"
if not defined ISCC for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do if not defined ISCC set ISCC="%%I"

if not defined ISCC (
    echo ERROR: Inno Setup compiler not found.
    echo Checked:
    echo   !ISCC_PROGRAMFILES!
    echo   !ISCC_PROGRAMFILES_X86!
    echo   !ISCC_LOCALAPPDATA!
    echo   PATH lookup for ISCC.exe
    echo Install Inno Setup 6 from: https://jrsoftware.org/isinfo.php
    popd
    exit /b 1
)

if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
set PYTHONPATH=%CD%\src

if exist "assets\branding\installer.ico" set INSTALLER_ICON=..\assets\branding\installer.ico

for /f %%I in ('%PYTHON% -c "from lap_coach_logger.app_identity import VERSION; print(VERSION)"') do set APP_VERSION=%%I

if not exist dist\LapCoachLogger\LapCoachLogger.exe (
    echo ERROR: Build output missing. Run build.bat first.
    popd
    exit /b 1
)

%ISCC% /DAppVersion=%APP_VERSION% /DSetupIconFile=%INSTALLER_ICON% %ISS%
if errorlevel 1 (
    echo ERROR: Installer build failed.
    popd
    exit /b 1
)

echo Installer build complete.
popd
