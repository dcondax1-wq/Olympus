@echo off
rem ALERTS SETUP (double-click, once): your trade alerts on Telegram and / or Discord (engine\alert_bus.py).
rem Asks 1 Telegram, 2 Discord, 3 both. The BotFather token / the webhook URL is pasted HIDDEN (nothing shows as you type),
rem saved ONLY in %USERPROFILE%\.olympus\alerts.json (never this folder, never GitHub) and never printed. Then a test alert.
rem Telegram: tap START in your bot within 3 minutes. Messages you send to the bot are ignored (no commands, no trading).
setlocal EnableExtensions
title Olympus - ALERTS SETUP
cd /d "%~dp0"
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" -X utf8 tools\alerts_setup.py setup
echo.
pause
endlocal
