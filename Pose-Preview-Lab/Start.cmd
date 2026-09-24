@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "RUNTIME="
if exist ".venv\Scripts\python.exe" set "RUNTIME=%CD%\.venv\Scripts\python.exe"
if defined RUNTIME goto launch
if exist "..\.venv\Scripts\python.exe" set "RUNTIME=%CD%\..\.venv\Scripts\python.exe"
if defined RUNTIME goto check
if exist "..\..\osr-screen-tcode\.venv\Scripts\python.exe" set "RUNTIME=%CD%\..\..\osr-screen-tcode\.venv\Scripts\python.exe"
if defined RUNTIME goto check
goto setup
:check
"%RUNTIME%" -c "import tkinter, cv2, numpy, PIL, mss, rtmlib, onnxruntime" >nul 2>nul
if not errorlevel 1 goto launch
:setup
set "PYTHON=py -3"
py -3 -c "import sys" >nul 2>nul
if errorlevel 1 set "PYTHON=python"
%PYTHON% -m venv .venv
if errorlevel 1 goto failed
set "RUNTIME=%CD%\.venv\Scripts\python.exe"
echo Installing preview dependencies locally. No models are downloaded.
"%RUNTIME%" -m pip install -r requirements.txt
if errorlevel 1 goto failed
:launch
"%RUNTIME%" preview.py %*
if errorlevel 1 goto failed
exit /b 0
:failed
echo Preview startup failed. Python 3.10+ and the dependencies are required.
echo Keep this window open to read the error above.
pause
exit /b 1
