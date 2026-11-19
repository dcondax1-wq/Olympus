@echo off
rem KALSHI STOP (double-click). Cancels every resting Kalshi order and switches Kalshi OFF (the kill switch). What Kalshi
rem holds stays (it settles by itself; to sell it now use FLATTEN on the phone's ZEUS Safety page). Start again only with
rem KALSHI_LIVE.bat and the typed phrase. Code: engine\kalshi_live.py --stop
setlocal EnableExtensions
title Kalshi - STOP
cd /d "%~dp0"
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
