@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_CMD="

py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo.
    echo Python 3.10 or newer was not found.
    echo Install Python from https://www.python.org/downloads/windows/
    echo Then run this file again.
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating local Python environment...
    call %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo.
        echo Failed to create the local Python environment.
        echo.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
    echo.
    echo The existing .venv uses an unsupported Python version.
    echo Delete the .venv folder, then run this file again.
    echo.
    pause
    exit /b 1
)

echo Installing or updating dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Failed to install the required dependencies.
    echo Check your network connection, then run this file again.
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -c "import mss, numpy, cv2, serial, bleak, PIL, sounddevice, soundcard, websockets, rtmlib, onnxruntime" >nul 2>nul
if errorlevel 1 (
    echo Repairing local dependencies...
    ".venv\Scripts\python.exe" -m pip install --force-reinstall --no-cache-dir -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Failed to repair the required dependencies.
        echo.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -c "import mss, numpy, cv2, serial, bleak, PIL, sounddevice, soundcard, websockets, rtmlib, onnxruntime" >nul 2>nul
    if errorlevel 1 (
        echo.
        echo Failed to import the required dependencies.
        echo.
        pause
        exit /b 1
    )
)

set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m osr_screen_tcode %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo The app closed with error code %EXIT_CODE%.
    echo.
    pause
)
exit /b %EXIT_CODE%
