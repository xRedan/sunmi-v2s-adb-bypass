@echo off
setlocal
cd /d "%~dp0"
echo Read boot-related partitions. Run as administrator and follow the connection instructions.
call "%~dp0run.cmd" "%~dp0scripts\backup_partitions.py" --read
set "TASK_EXIT=%ERRORLEVEL%"
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
