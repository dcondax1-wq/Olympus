@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem POSTCARD STOP (double-click). Switches the postcards OFF: no card is sent until POSTCARD_SETUP.bat again. The email autopilot is separate
rem (EMAIL_STOP.bat). Your settings and the never-again list stay.
setlocal EnableExtensions
title Agency - POSTCARD STOP
cd /d "%LE_HOME%"
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" -X utf8 tools\postcards.py stop
echo.
pause
endlocal
