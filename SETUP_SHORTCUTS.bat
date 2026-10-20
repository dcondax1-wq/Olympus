@echo off
rem Liquidity Engine: one-time setup (double-click once). Puts 4 icons on the desktop (UPDATE, DASHBOARD, HEALTH CHECK,
rem STOP BOT) and adds the 5-minute helper task (phone notices: pre-session check, day / week summary, internet and
rem NinjaTrader drops, MFFU reminders; nightly backup). Run it again any time: it replaces what it made before.
setlocal EnableExtensions
title Liquidity Engine - SETUP
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\make_shortcuts.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_ops_task.ps1"
echo.
pause
endlocal
