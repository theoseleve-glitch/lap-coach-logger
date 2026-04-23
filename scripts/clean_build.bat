@echo off
REM Wipe all PyInstaller + Inno Setup outputs to force a clean rebuild.
REM Safe to run repeatedly; does not touch source.
setlocal
pushd "%~dp0\.."

echo === Cleaning build artifacts ===
if exist build\LapCoachLogger  rmdir /S /Q build\LapCoachLogger
if exist dist                  rmdir /S /Q dist
if exist build\windows\version_info.txt del /Q build\windows\version_info.txt
for /d /r src %%D in (__pycache__) do if exist "%%D" rmdir /S /Q "%%D"
for /d /r tests %%D in (__pycache__) do if exist "%%D" rmdir /S /Q "%%D"
if exist .pytest_cache rmdir /S /Q .pytest_cache
if exist LapCoachLogger-Setup-*.exe del /Q LapCoachLogger-Setup-*.exe

echo === Clean complete ===
popd
endlocal
