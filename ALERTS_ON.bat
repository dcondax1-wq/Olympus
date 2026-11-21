@echo off
rem ALERTS ON (double-click): the alert bus back on (Telegram / Discord first, ntfy + the Olympus app as backups).
setlocal EnableExtensions
title Olympus - ALERTS ON
cd /d "%~dp0"
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" -X utf8 tools\alerts_setup.py on
echo.
pause
endlocal
