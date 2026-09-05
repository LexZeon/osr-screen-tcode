@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src"
set "RUNTIME="

if exist ".venv\Scripts\python.exe" (
    set "RUNTIME=%CD%\.venv\Scripts\python.exe"
    goto check_runtime
)

rem Reuse the sibling source runtime read-only when developing locally.
rem Never install or update packages in that shared environment.
if exist "..\osr-screen-tcode\.venv\Scripts\python.exe" (
    "..\osr-screen-tcode\.venv\Scripts\python.exe" -c "import tkinter, mss, numpy, cv2, serial, bleak, PIL, sounddevice, soundcard, websockets, rtmlib, onnxruntime" >nul 2>nul
    if not errorlevel 1 (
        set "RUNTIME=%CD%\..\osr-screen-tcode\.venv\Scripts\python.exe"
        goto launch
    )
)

set "PYTHON_CMD="
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo Python 3.10 or newer is required for source startup.
    echo Install it from https://www.python.org/downloads/windows/
    goto failed
)
call %PYTHON_CMD% -m venv .venv
if errorlevel 1 goto failed
set "RUNTIME=%CD%\.venv\Scripts\python.exe"

:check_runtime
"%RUNTIME%" -c "import sys, tkinter, mss, numpy, cv2, serial, bleak, PIL, sounddevice, soundcard, websockets, rtmlib, onnxruntime; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 goto launch
echo Installing dependencies in this test folder...
"%RUNTIME%" -m pip install -r requirements.txt
if errorlevel 1 goto failed
"%RUNTIME%" -c "import tkinter, mss, numpy, cv2, serial, bleak, PIL, sounddevice, soundcard, websockets, rtmlib, onnxruntime" >nul 2>nul
if errorlevel 1 goto failed

:launch
echo Starting SR6/OSR6 Realtime Screen TCode High Hardware Compatibility v2.0.0-test.3...
"%RUNTIME%" -m osr_screen_tcode %*
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" goto failed
exit /b 0

:failed
echo.
echo Startup failed. Please keep this window open to read the error above.
pause
exit /b 1
