@echo off
setlocal
pushd "%~dp0"
call build.bat %*
set EXITCODE=%ERRORLEVEL%
popd
exit /b %EXITCODE%