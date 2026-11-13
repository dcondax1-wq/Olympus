@echo off
rem Liquidity Engine: LIVE LINK (double-click). Your live dashboard on the iPhone, private and free: Tailscale (free personal plan)
rem connects the phone to the bot server on THIS PC (https://<this-pc>.<tailnet>.ts.net/, your own devices only, never the
rem internet). It checks Tailscale is installed and signed in (opens the download / sign-in page if not), turns the link on,
rem keeps the site fresh every 15 minutes and prints the address to open on the phone. Read only over the link: nothing on the
rem phone can start, stop or arm a bot. Safe to run again. Undo: UNDO_LIVE_LINK.bat. docs\LIVE_DASHBOARD.md
setlocal EnableExtensions
title Liquidity Engine - LIVE LINK
cd /d "%~dp0"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
if not exist "%~dp0scripts\live_link.ps1" goto :old
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\live_link.ps1" %* & echo. & pause & exit /b

:old
echo  [FIX] This bot folder has old code. Put the new code zip in Downloads and double-click UPDATE_FROM_ZIP.bat first,
echo        then double-click LIVE_LINK.bat again. Nothing was changed.
echo.
pause
exit /b

:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
echo.
pause
endlocal
