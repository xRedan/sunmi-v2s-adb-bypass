@echo off
setlocal
cd /d "%~dp0"
echo Install the official full Magisk APK through ADB.
call "%~dp0run.cmd" "%~dp0scripts\toolkit.py" install-magisk --apply
set "TASK_EXIT=%ERRORLEVEL%"
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
