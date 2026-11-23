@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem Liquidity Engine: UNDO PC TUNE (double-click). Puts back every change the v2 deep tune of CLEAN_PC.bat made: the power
rem plan, services, memory settings, Defender folder exclusions, network power saving, Edge / Chrome / Office settings,
rem Storage Sense and the two helper tasks, AND everything PC_CARE.bat changed (its power plan, startup apps, background
rem apps, visual effects, search-indexing pause). It reads the lists it saved before each change:
rem %ProgramData%\LiquidityEngine\pc_tune_state.json. Windows asks once for Administrator: click Yes.
rem It also switches Obsidian back on at sign-in if an older CLEAN_PC switched it off. Safe any time (also while the
rem bot trades). NinjaTrader and the bot are never touched. docs\PC_PERFORMANCE.md
setlocal EnableExtensions
title Liquidity Engine - UNDO PC TUNE
cd /d "%LE_HOME%"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
rem PC_CARE.bat first (it is the newer one; its power plan may sit on top of the deep tune's), then the deep tune
if exist "%LE_HOME%scripts\pc_care.ps1" powershell -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\pc_care.ps1" -Undo & goto :tune
if exist "%LOCALAPPDATA%\LiquidityEngine\pc_care.ps1" powershell -NoProfile -ExecutionPolicy Bypass -File "%LOCALAPPDATA%\LiquidityEngine\pc_care.ps1" -Undo
:tune
powershell -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\clean_pc.ps1" -Undo & echo. & pause & exit /b

:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
echo.
pause
endlocal
