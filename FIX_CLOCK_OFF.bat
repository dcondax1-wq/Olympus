@echo off
rem FIX THE CLOCK, UNDO: removes the task OlympusClock (right-click > Run as administrator). Windows keeps its own
rem time service on Automatic. Run FIX_CLOCK.bat again any time.
setlocal EnableExtensions
title Olympus - FIX THE CLOCK (undo)
cd /d "%~dp0"
net session >nul 2>&1
if errorlevel 1 goto :noadmin
where powershell >nul 2>&1
if errorlevel 1 goto :nops
if not exist "%~dp0scripts\fix_clock.ps1" goto :nofile
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\fix_clock.ps1" -Off
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
