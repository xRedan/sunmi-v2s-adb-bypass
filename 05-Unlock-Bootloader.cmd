@echo off
setlocal
cd /d "%~dp0"
echo Native unlock. ERASES USER DATA if still locked. Run as administrator.
call "%~dp0run.cmd" "%~dp0scripts\toolkit.py" unlock --apply
set "TASK_EXIT=%ERRORLEVEL%"
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
