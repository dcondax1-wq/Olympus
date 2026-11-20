@echo off
rem Olympus: CALLER STOP. Turns the AI caller OFF at once (no new call starts), stops its server and its public address.
rem Safe to run any time, as often as you like. It never touches trading, NinjaTrader or the bot.
setlocal EnableExtensions
title Olympus - CALLER STOP
cd /d "%~dp0"
set "TS=tailscale"
where tailscale >nul 2>&1
if errorlevel 1 set "TS=%ProgramFiles%\Tailscale\tailscale.exe"
where python >nul 2>&1
if errorlevel 1 goto :kill
python -X utf8 -m tools.caller.onoff off

:kill
taskkill /FI "WINDOWTITLE eq Olympus caller*" /T /F >nul 2>&1
"%TS%" funnel --https=10000 off >nul 2>&1
echo.
echo  [OK] AI caller is OFF.
echo.
pause
exit /b 0
