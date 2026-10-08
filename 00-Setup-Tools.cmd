@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1" %*
set "TASK_EXIT=%ERRORLEVEL%"
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
