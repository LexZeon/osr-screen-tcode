@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "%~dp0Start-Source.cmd" (
    echo Start-Source.cmd is missing. Restore the complete source folder.
    pause
    exit /b 1
)
call "%~dp0Start-Source.cmd" %*
exit /b %ERRORLEVEL%
