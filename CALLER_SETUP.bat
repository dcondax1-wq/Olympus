@echo off
rem Olympus: CALLER SETUP (double-click once). Saves the AI caller's keys ONLY in %USERPROFILE%\.olympus\caller.json (never in the repo,
rem never shown as you paste): Twilio Account SID, Twilio Auth Token, your Twilio phone number, Claude API key.
rem It never calls anyone and never turns the caller on. Plan + law: research\writeups\ai-caller-2026-11-20.md
setlocal EnableExtensions
title Olympus - CALLER SETUP
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 goto :nopy
python -X utf8 -m tools.caller.setup_keys
if errorlevel 1 goto :fix
echo.
echo  Next (one time, free): the federal Do-Not-Call list for your 5 free area codes.
echo   1. Sign up at telemarketing.donotcall.gov as a "seller" (free for up to 5 area codes).
echo   2. Download 301, 240, 410, 443, 667 (Maryland) as text files.
echo   3. Put them in %USERPROFILE%\.olympus\caller\registry\ as 301.txt, 240.txt, ...
echo      and run:  python -m tools.caller.registry   (it writes the date; re-download every 31 days)
echo.
echo  Then CALLER_ON.bat. Nothing is called until you type START CALLING there.
echo.
pause
exit /b 0

:fix
echo.
echo  [FIX] Nothing saved. Run CALLER_SETUP.bat again and paste each key carefully.
pause
exit /b 1

:nopy
echo  [FIX] Python not found. Run ONE_TIME_SETUP.bat first.
pause
exit /b 1
