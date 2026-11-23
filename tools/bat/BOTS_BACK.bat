@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem Liquidity Engine: BOTS BACK (double-click). The bots and their reporting without GitHub, in one go: GitHub pushes off,
rem NinjaTrader and its LE_BarFeed bars checked, the bot server started (a paper / Sim start resumed; a real account is never
rem armed here), the 15-minute phone report installed, then six lines: bots, feed, last trade, drawdown left, reporting, next
rem window. Safe to double-click again: done steps are skipped and a running bot is left alone. Undo: UNDO_BOTS_BACK.bat.
rem docs\BOTS_BACK.md. The work is done by scripts\bots_back.ps1.
setlocal EnableExtensions
title Liquidity Engine - BOTS BACK
cd /d "%LE_HOME%"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
if not exist "%LE_HOME%scripts\bots_back.ps1" goto :old
powershell -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\bots_back.ps1" %* & echo. & pause & exit /b

:old
echo  [FIX] This bot folder has old code. Put the new code zip in Downloads and double-click UPDATE_FROM_ZIP.bat first
echo        (it is in the zip; docs\BOTS_BACK.md step 1), then double-click BOTS_BACK.bat again. Nothing was changed.
echo.
pause
exit /b

:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
echo.
pause
endlocal
