@echo off
setlocal
pushd "%~dp0"

call package.bat %*
if errorlevel 1 (
    popd
    exit /b 1
)

call build_installer.bat
set EXITCODE=%ERRORLEVEL%

popd
exit /b %EXITCODE%