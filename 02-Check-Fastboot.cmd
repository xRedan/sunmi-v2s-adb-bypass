@echo off
setlocal
cd /d "%~dp0"
echo Read-only bootloader Fastboot check.
call "%~dp0run.cmd" "%~dp0scripts\toolkit.py" check-fastboot --apply
set "TASK_EXIT=%ERRORLEVEL%"
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
