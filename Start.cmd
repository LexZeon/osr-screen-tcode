@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if exist "%~dp0OSR6-Realtime-Screen.exe" (
    echo Starting OSR6 Realtime Screen TCode...
    start "OSR6 Realtime Screen TCode" /D "%~dp0" "%~dp0OSR6-Realtime-Screen.exe" %*
    if errorlevel 1 (
        echo.
        echo Failed to start OSR6-Realtime-Screen.exe.
        echo Please make sure the zip has been fully extracted before running.
        pause
        exit /b 1
    )
    timeout /t 2 /nobreak >nul
    exit /b 0
)

if not exist "%~dp0Start-Source.cmd" (
    echo.
    echo OSR6-Realtime-Screen.exe was not found.
    echo Start-Source.cmd was not found either.
    echo Please extract the whole package before running Start.cmd.
    pause
    exit /b 1
)

call "%~dp0Start-Source.cmd" %*
if errorlevel 1 (
    echo.
    echo Source startup failed. Please keep this window open and send the message above.
    pause
)
exit /b %ERRORLEVEL%
