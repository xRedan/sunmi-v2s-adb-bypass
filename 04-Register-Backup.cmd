@echo off
setlocal
cd /d "%~dp0"
echo Select and verify the original backup folder. No USB access.
call "%~dp0run.cmd" "%~dp0scripts\register_backup.py" 
set "TASK_EXIT=%ERRORLEVEL%"
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
