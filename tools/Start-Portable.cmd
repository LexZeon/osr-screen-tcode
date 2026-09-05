@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "%~dp0SR6-OSR6-Realtime-Screen-TCode-High-Hardware-Compatibility.exe" (
    echo The application is missing. Extract the complete Windows ZIP first.
    pause
    exit /b 1
)
start "" "%~dp0SR6-OSR6-Realtime-Screen-TCode-High-Hardware-Compatibility.exe" %*
exit /b 0
