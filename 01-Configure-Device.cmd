@echo off
setlocal
cd /d "%~dp0"
echo Configure the device serial locally. No backup or USB access required.
call "%~dp0run.cmd" "%~dp0scripts\toolkit.py" configure
set "TASK_EXIT=%ERRORLEVEL%"
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
