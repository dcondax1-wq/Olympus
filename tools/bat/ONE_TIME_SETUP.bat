@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem Liquidity Engine: ONE TIME SETUP (double-click once, at the Surface). Stops the bot, updates it from main, sets the
rem power plan (never sleep on AC), Windows Update (paused, no restart while trading), the start-at-logon tasks, NinjaTrader
rem at logon, the desktop icons and auto-update, starts the bot (asks your eval account and your phrase, hidden; Enter =
rem Sim101 practice) and runs the health check. Windows asks once for Administrator: click Yes. Steps: docs\ONE_TIME_SETUP.md
rem The setup pulls new code, which can rewrite this very file while it runs (cmd.exe reads a .bat line by line from its
rem byte offset), so the PowerShell call, the pause and the exit are ONE line: cmd has read all of it before the pull.
setlocal EnableExtensions
title Liquidity Engine - ONE TIME SETUP
cd /d "%LE_HOME%"
set "PYTHONIOENCODING=utf-8"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
powershell -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\one_time_setup.ps1" & echo. & pause & exit /b

:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
echo.
pause
endlocal
