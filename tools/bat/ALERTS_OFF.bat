@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem ALERTS OFF (double-click): the alert bus off; alerts take the old path (ntfy + the Olympus app) exactly as before.
rem ALERTS_ON.bat turns it back on. Nothing about trading changes.
setlocal EnableExtensions
title Olympus - ALERTS OFF
cd /d "%LE_HOME%"
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" -X utf8 tools\alerts_setup.py off
echo.
pause
endlocal
