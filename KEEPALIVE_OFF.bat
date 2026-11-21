@echo off
rem MFFU 7-day keep-alive OFF for every account (double-click). After this the bot never places a keep-alive trade;
rem you get the phone warning from day 5 instead and place a small trade yourself. KEEPALIVE_ON.bat turns it back on.
setlocal EnableExtensions
cd /d "%~dp0"
title Liquidity Engine - 7-DAY KEEP-ALIVE OFF
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
echo.
"%PY%" -X utf8 -m engine.keepalive --off all || goto :fail
echo.
echo  [OK] Keep-alive is OFF on every account.
goto :end
:fail
echo.
echo  [NOT CHANGED] See the line above.
:end
echo.
pause
