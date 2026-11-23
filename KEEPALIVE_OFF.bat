@echo off
rem MFFU 7-day keep-alive OFF for every account (double-click). After this the bot never places a keep-alive trade;
rem you get the phone warning from day 5 instead and place a small trade yourself. KEEPALIVE_ON.bat turns it back on
rem (START BOT's I ACCEPT LIVE RISK turns the keep-alive on for the accounts it arms, but never after this OFF).
setlocal EnableExtensions
cd /d "%~dp0"
title Liquidity Engine - 7-DAY KEEP-ALIVE OFF
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
echo.
"%PY%" -X utf8 -m engine.keepalive --off all || goto :fail
echo.
echo  [OK] Keep-alive is OFF on every account. It stays off: a START with the phrase does not turn it back on.
goto :end
:fail
echo.
echo  [NOT CHANGED] See the line above.
:end
echo.
pause
