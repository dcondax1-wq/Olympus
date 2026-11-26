@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem NINJATRADER OUT OF ONEDRIVE (day-ops2): pins the NinjaTrader 8 folder (always on this PC), then asks before moving it out of
rem OneDrive (NinjaTrader closed, after 16:00 ET, bots flat; a junction keeps the old path working; backup kept). No administrator.
rem Undo: NT_OFF_ONEDRIVE.bat undo
setlocal EnableExtensions
title Olympus - NinjaTrader out of OneDrive
cd /d "%LE_HOME%"
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if /i "%~1"=="undo" ( "%PS%" -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\nt_off_onedrive.ps1" -Undo & echo. & pause & exit /b )
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\nt_off_onedrive.ps1"
echo.
echo  Also move the NinjaTrader folder OUT of OneDrive for good? Close NinjaTrader first. Type Y then Enter (anything else = no):
set /p ANS=
if /i "%ANS%"=="Y" "%PS%" -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\nt_off_onedrive.ps1" -Move
echo.
pause
endlocal
