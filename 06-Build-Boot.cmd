@echo off
setlocal
cd /d "%~dp0"
echo Build and verify the modified boot offline. No USB access.
call "%~dp0run.cmd" "%~dp0scripts\rebuild_boot.py" 
set "TASK_EXIT=%ERRORLEVEL%"
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
