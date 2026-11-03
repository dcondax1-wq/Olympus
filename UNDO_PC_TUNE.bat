@echo off
rem Liquidity Engine: UNDO PC TUNE (double-click). Puts back every change the v2 deep tune of CLEAN_PC.bat made: the power
rem plan, services, memory settings, Defender folder exclusions, network power saving, Edge / Chrome / Office settings,
rem Storage Sense and the two helper tasks. It reads the list it saved before each change:
rem %ProgramData%\LiquidityEngine\pc_tune_state.json. Windows asks once for Administrator: click Yes.
rem It also switches Obsidian back on at sign-in if an older CLEAN_PC switched it off. Safe any time (also while the
rem bot trades). NinjaTrader and the bot are never touched. docs\PC_PERFORMANCE.md
setlocal EnableExtensions
title Liquidity Engine - UNDO PC TUNE
cd /d "%~dp0"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\clean_pc.ps1" -Undo & echo. & pause & exit /b

:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
echo.
pause
endlocal
