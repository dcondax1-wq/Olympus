@echo off
rem KALSHI LIVE (double-click). Real money, small: it shows the plan, its limits (checked before every order) and what it
rem would place right now, then YOU type the phrase I ACCEPT KALSHI LIVE RISK. Only then it starts, in the background.
rem It switches itself OFF after any stop (daily loss stop, kill switch, phone FLATTEN / KILL, a plan change): then you type
rem the phrase again. Claude never types it and this file never arms anything by itself.
rem Stop: KALSHI_STOP.bat or the phone's ZEUS Safety page. Key first: KALSHI_KEY_SETUP.bat. Code: engine\kalshi_live.py
setlocal EnableExtensions
title Kalshi - GO LIVE
cd /d "%~dp0"
if not exist "%~dp0engine\kalshi_live.py" goto :old
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" -X utf8 -m engine.kalshi_live --go
echo.
pause
endlocal
exit /b

:old
echo  [FIX] This bot folder has old code. Double-click UPDATE.bat first, then KALSHI_LIVE.bat again. Nothing was changed.
echo.
pause
exit /b
