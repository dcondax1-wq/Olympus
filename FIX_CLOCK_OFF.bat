@echo off
rem FIX THE CLOCK, UNDO: removes the task OlympusClock and puts the Windows time settings back to the Windows defaults
rem (right-click > Run as administrator). Windows keeps its own time service on Automatic. Run FIX_CLOCK.bat again any time.
setlocal EnableExtensions
title Olympus - FIX THE CLOCK (undo)
cd /d "%~dp0"
rem full paths only: this window is elevated and the bot folder is user-writable (no program is looked up in it)
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
"%SystemRoot%\System32\net.exe" session >nul 2>&1
if errorlevel 1 goto :noadmin
if not exist "%PS%" goto :nops
if not exist "%~dp0scripts\fix_clock.ps1" goto :nofile
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\fix_clock.ps1" -Off
goto :end
:noadmin
echo.
echo  [FIX] This needs an administrator. Close this window, then right-click FIX_CLOCK_OFF.bat and choose "Run as administrator".
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
