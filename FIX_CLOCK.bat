@echo off
rem FIX THE CLOCK (owner 2026-11-22): run ONCE, right-click > Run as administrator. Sets Windows' time service to Automatic, the
rem time servers, a 15-minute poll, syncs now and registers the task OlympusClock (SYSTEM, every 15 min + boot + wake) so the
rem bot's clock guard never needs you again. Prints the drift before and after. Safe to run twice. Undo: FIX_CLOCK_OFF.bat.
setlocal EnableExtensions
title Olympus - FIX THE CLOCK
cd /d "%~dp0"
net session >nul 2>&1
if errorlevel 1 goto :noadmin
where powershell >nul 2>&1
if errorlevel 1 goto :nops
if not exist "%~dp0scripts\fix_clock.ps1" goto :nofile
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\fix_clock.ps1"
goto :end
:noadmin
echo.
echo  [FIX] This needs an administrator. Close this window, then right-click FIX_CLOCK.bat and choose "Run as administrator".
goto :end
:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
goto :end
:nofile
echo  [FIX] scripts\fix_clock.ps1 is missing: double-click UPDATE.bat, then try again.
:end
echo.
pause
endlocal
