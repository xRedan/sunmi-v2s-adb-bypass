@echo off
setlocal
cd /d "%~dp0"
echo Verify tool checksums offline.
call "%~dp0run.cmd" "%~dp0scripts\toolkit.py" verify-tools
set "TASK_EXIT=%ERRORLEVEL%"
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
