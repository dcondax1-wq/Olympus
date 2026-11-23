@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem Liquidity Engine: CLEAN PC (double-click). Makes the Surface lighter for NinjaTrader and the bot: closes and stops at
rem sign-in the programs trading does not need, a lighter Windows, junk files; the deep part (Windows asks once for
rem Administrator: click Yes) and the v2 deep tune (power plan, services, memory, Defender, network; undo: UNDO_PC_TUNE.bat)
rem run only outside trading hours. NinjaTrader and the bot are never touched.
rem What it does: scripts\clean_pc.ps1 (top of the file). Log: logs\clean_pc-YYYYMMDD-HHMM.txt
rem Main PC (no bot folder): the same two files (the PC_KIT folder) run STANDALONE by themselves. It also writes
rem PC_REPORT-<computer>.txt (what the PC is) and a read-only NinjaTrader check. docs\PC_PERFORMANCE.md
setlocal EnableExtensions
title Liquidity Engine - CLEAN PC
cd /d "%LE_HOME%"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
powershell -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\clean_pc.ps1" & echo. & pause & exit /b

:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
echo.
pause
endlocal
