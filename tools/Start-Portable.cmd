@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "%~dp0SR6-OSR6-Realtime-Screen-TCode.exe" (
    echo Extract the complete Windows ZIP, then use Start.cmd INSIDE that folder.
    echo This launcher alone does not contain the application.
    echo See Start.md for English and Chinese startup instructions.
    pause
    exit /b 1
)
if not exist "%~dp0_internal" (
    echo The runtime folder is missing. Extract the complete Windows ZIP first.
    echo See Start.md for English and Chinese startup instructions.
    pause
    exit /b 1
)
start "" "%~dp0SR6-OSR6-Realtime-Screen-TCode.exe" %*
exit /b 0
