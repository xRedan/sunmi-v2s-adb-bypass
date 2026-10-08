@echo off
setlocal
cd /d "%~dp0"
echo Reboot from bootloader Fastboot after checking device identity.
call "%~dp0run.cmd" "%~dp0scripts\toolkit.py" reboot --apply
set "TASK_EXIT=%ERRORLEVEL%"
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
