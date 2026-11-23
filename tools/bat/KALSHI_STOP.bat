@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem KALSHI STOP (double-click). Cancels every resting Kalshi order and switches Kalshi OFF (the kill switch). What Kalshi
rem holds stays (it settles by itself; to sell it now use FLATTEN on the phone's ZEUS Safety page). Start again only with
rem KALSHI_LIVE.bat and the typed phrase. Code: engine\kalshi_live.py --stop
setlocal EnableExtensions
title Kalshi - STOP
cd /d "%LE_HOME%"
echo.
echo  This cancels every resting Kalshi order and switches Kalshi OFF.
echo.
set "ANS="
set /p "ANS= Type Y then Enter to stop Kalshi: "
if /i not "%ANS%"=="Y" goto :cancel
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" -X utf8 -m engine.kalshi_live --stop
goto :end

:cancel
echo  Nothing stopped.

:end
echo.
pause
endlocal
