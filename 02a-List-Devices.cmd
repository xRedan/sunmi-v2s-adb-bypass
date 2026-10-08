@echo off
setlocal
cd /d "%~dp0"
echo Read-only list of connected Fastboot devices.
call "%~dp0run.cmd" "%~dp0scripts\toolkit.py" devices --apply
set "TASK_EXIT=%ERRORLEVEL%"
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
