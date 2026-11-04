@echo off
rem BOT LITE (double-click): the bot on very little memory. LITE mode on (read-only add-ons off, 100 days of history;
rem trades exactly the same), NinjaTrader started, the bot server started or restarted when flat (never during a trade,
rem never arms anything), NinjaTrader + the bot first in Windows, then a short NinjaTrader memory checklist.
rem Back to the full bot: BOT_LITE.bat -Off   What it does: scripts\bot_lite.ps1 (top of the file), engine\lite.py
setlocal EnableExtensions
title Zlarior + ATLAS - BOT LITE
cd /d "%~dp0"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bot_lite.ps1" %* & echo. & pause & exit /b

:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
echo.
pause
endlocal
