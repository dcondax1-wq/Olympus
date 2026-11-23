@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem Liquidity Engine: one-time setup (double-click once). Puts 2 icons on the desktop (LE START = the dashboard's Start
rem page, LE STOP BOT; the older icons are removed) and adds the 5-minute helper task (phone notices: pre-session check,
rem day / week summary, internet and NinjaTrader drops, MFFU reminders; nightly backup). Run it again any time: it
rem replaces what it made before.
setlocal EnableExtensions
title Liquidity Engine - SETUP
cd /d "%LE_HOME%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\make_shortcuts.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\install_ops_task.ps1"
echo.
pause
endlocal
