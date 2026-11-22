@echo off
rem TRADING HOME: ONE double-click menu for every daily PC step (owner 2026-11-22). 1 Status, 2 Start bot, 3 Keep-alive on,
rem 4 Add an account, 5 Phone alerts, 6 Stop bot, 7 Update, 8 the whole Sunday / daily routine. Each number just CALLS the
rem existing .bat; you type every live phrase yourself in that step's own window. Uses scripts\trade_home.ps1 -> engine\trade_home.py.
setlocal EnableExtensions
title Olympus - TRADING HOME
cd /d "%~dp0"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\trade_home.ps1"
goto :end
:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
:end
echo.
pause
endlocal
