@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem OLYMPUS: CONNECT YOUR DAY (double-click). Paste the read-only addresses of your calendars (Google "Secret address in iCal
rem format", an iCloud public calendar link, an Outlook ICS link, your shift app's calendar link), your city and your pay. They are
rem kept in %USERPROFILE%\.olympus\calendars.json on this PC only (never uploaded, never in the bot folder). No password is asked.
rem The PC report task then reads them every 15 minutes; the phone sees your day through the PC's own link. docs\CONNECT_DAY.md
setlocal EnableExtensions
title OLYMPUS - Connect your day
cd /d "%LE_HOME%"
where python >nul 2>&1
if errorlevel 1 goto :nopy
python -X utf8 tools\calendar_sync.py --setup
echo.
pause
exit /b

:nopy
echo  [FIX] Python not found. Run ONE_TIME_SETUP.bat first, or send Claude a photo of this window.
echo.
pause
endlocal
