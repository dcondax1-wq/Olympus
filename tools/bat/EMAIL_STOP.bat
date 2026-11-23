@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem EMAIL STOP (double-click). Switches the Website Factory email autopilot OFF and removes its task OlympusAgencyMail.
rem Nothing is sent again until EMAIL_SETUP.bat and the typed phrase SEND EMAILS. Your settings and the never-again list stay.
setlocal EnableExtensions
title Agency - EMAIL STOP
cd /d "%LE_HOME%"
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" -X utf8 -m agency.autopilot stop
powershell -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\agency_mail_task.ps1" -Remove
echo.
pause
endlocal
