@echo off
rem Liquidity Engine: stop the bot and the dashboard server (double-click). An open trade keeps its stop and target in
rem NinjaTrader. After this the bot stays stopped (no auto-resume) until you start it again.
setlocal EnableExtensions
title Liquidity Engine - STOP
cd /d "%~dp0"
echo.
echo  This stops the bot and the dashboard.
echo  An open trade keeps its stop and target in NinjaTrader, but the bot no longer moves the stop to breakeven.
echo.
set "ANS="
set /p "ANS= Type Y then Enter to stop: "
if /i not "%ANS%"=="Y" goto :cancel
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_bot.ps1"
echo.
echo  [OK]  Stopped. Start again with START_DASHBOARD, then press Start on the dashboard.
goto :end

:cancel
echo  Nothing stopped.

:end
echo.
pause
endlocal
