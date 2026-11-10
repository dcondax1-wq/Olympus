@echo off
rem Liquidity Engine: PUBLISH NQ (double-click). The NQ reporting without GitHub: sets up the 15-minute task that builds the NQ
rem state and the site on THIS PC and publishes it (Netlify or a synced folder, your choice in the settings folder), switches the
rem bot to GitHub-free mode (takes effect at the bot's next start), then publishes once now and shows six lines. Safe to run
rem again any time. It never starts, stops or arms the bot and never touches NinjaTrader or an order. docs\NQ_BOT_BACK.md
setlocal EnableExtensions
title Liquidity Engine - PUBLISH NQ
cd /d "%~dp0"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\publish_nq.ps1" %* & echo. & pause & exit /b

:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
echo.
pause
endlocal
