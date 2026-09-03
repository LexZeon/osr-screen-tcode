@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if exist "%~dp0OSR6-Realtime-Screen.exe" (
    start "" "%~dp0OSR6-Realtime-Screen.exe" %*
    exit /b 0
)

call "%~dp0Start-Source.cmd" %*
exit /b %ERRORLEVEL%
