@echo off
rem EMAIL SETUP (double-click, once). The Website Factory email autopilot on this PC: asks for a FREE business Gmail and its app
rem password (hidden as you type), your name, business, phone and postal address, a test address, then the phrase gate:
rem type SEND EMAILS to let it email businesses for real (max 20 new a day, Mon-Fri 9-16 ET, opt-outs honoured); anything else = DRY RUN
rem (every email goes to your own test address). It saves to %USERPROFILE%\.olympus (never the bot folder) and installs the 30-minute
rem task OlympusAgencyMail. It never touches the trading bot. Turn it off: EMAIL_STOP.bat. Code: agency\autopilot\run.py
setlocal EnableExtensions
title Agency - EMAIL SETUP
cd /d "%~dp0"
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" -X utf8 -m agency.autopilot setup
if errorlevel 1 goto :end
"%PY%" -X utf8 -m agency.autopilot test
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\agency_mail_task.ps1"
"%PY%" -X utf8 -m agency.autopilot status
:end
echo.
pause
endlocal
