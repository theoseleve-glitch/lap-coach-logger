@echo off
setlocal

set ROOT=%~dp0
set BUILD_DIR=%ROOT%build\native_frontend

if "%Qt6_DIR%"=="" (
  echo Qt6_DIR is not set.
  echo Point it to your Qt 6 CMake package directory, for example:
  echo   C:\Qt\6.8.0\msvc2022_64\lib\cmake\Qt6
  exit /b 1
)

if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"

set CMAKE_EXE=C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe

if not exist "%CMAKE_EXE%" (
  echo Could not find cmake.exe at:
  echo   %CMAKE_EXE%
  exit /b 1
)

"%CMAKE_EXE%" -S "%ROOT%native_frontend" -B "%BUILD_DIR%" -G Ninja -DCMAKE_PREFIX_PATH="%Qt6_DIR%"
if errorlevel 1 exit /b 1

"%CMAKE_EXE%" --build "%BUILD_DIR%" --config Release
if errorlevel 1 exit /b 1

echo Native frontend build complete.
