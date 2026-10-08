@echo off
setlocal
cd /d "%~dp0"
echo Select an APK and install it through ADB.
call "%~dp0run.cmd" "%~dp0scripts\toolkit.py" install-apk --apply
set "TASK_EXIT=%ERRORLEVEL%"
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
