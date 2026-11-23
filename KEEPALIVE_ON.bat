@echo off
rem MFFU 7-day keep-alive ON for every MFFU account (the owner's yes 2026-11-20). Double-click, read, type the phrase.
rem When an account has gone ~6 days without a trade, the bot places ONE 1-MNQ trade in and out on it (about -$2.40,
rem at most -$22.90) so MFFU's 7-day rule never closes it. Claude never runs this file: it allows real orders.
rem Undo any time: tools\bat\KEEPALIVE_OFF.bat. Uses engine/keepalive.py (--on all / --off all).
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Liquidity Engine - 7-DAY KEEP-ALIVE ON
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
echo.
echo  ==== MFFU 7-day keep-alive ====
"%PY%" -X utf8 -m engine.keepalive --on all
echo.
echo  It only trades an account that would otherwise hit 7 days with no trade. Your own trades reset its clock.
echo.
set "OK="
set /p OK=Type KEEP ALIVE ON and press Enter (anything else = nothing changes): 
if /i not "!OK!"=="KEEP ALIVE ON" goto :no
"%PY%" -X utf8 -m engine.keepalive --on all --yes || goto :fail
echo.
echo  [OK] Keep-alive is ON. The running bot picks it up within a minute; no restart needed.
goto :end
:no
echo.
echo  Nothing changed. The keep-alive stays as it was.
goto :end
:fail
echo.
echo  [NOT CHANGED] See the line above.
:end
echo.
pause
