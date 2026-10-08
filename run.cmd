@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.tools\python\python.exe" (
  echo Tools are missing. Run 00-Setup-Tools.cmd first.
  exit /b 2
)
"%~dp0.tools\python\python.exe" -B %*
exit /b %ERRORLEVEL%
