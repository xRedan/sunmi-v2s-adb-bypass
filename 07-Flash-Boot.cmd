@echo off
setlocal
cd /d "%~dp0"
echo PERSISTENT WRITE to boot_a. Run as administrator. Confirmation required.
call "%~dp0run.cmd" "%~dp0scripts\toolkit.py" install --apply
set "TASK_EXIT=%ERRORLEVEL%"
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
