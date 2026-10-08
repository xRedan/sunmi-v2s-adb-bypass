@echo off
setlocal
cd /d "%~dp0"
echo Read-only ADB check. Android must be running.
call "%~dp0run.cmd" "%~dp0scripts\toolkit.py" verify-adb --apply
set "TASK_EXIT=%ERRORLEVEL%"
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
