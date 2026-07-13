@echo off
rem Double-clickable launcher for the Blueprint Wizard (Windows).
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0blueprint_wizard.ps1" %*
set EXITCODE=%ERRORLEVEL%
rem When launched by double-click, keep the window open so results stay visible.
echo %cmdcmdline% | find /i "%~f0" >nul && pause
exit /b %EXITCODE%
