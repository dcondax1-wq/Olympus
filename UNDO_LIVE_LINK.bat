@echo off
rem Liquidity Engine: UNDO LIVE LINK (double-click). Turns the private phone link off (tailscale serve, only when it points at the
rem bot server) and removes the site task OlympusLiveSite. Tailscale stays installed and signed in. The bots are not touched.
rem docs\LIVE_DASHBOARD.md
setlocal EnableExtensions
title Liquidity Engine - UNDO LIVE LINK
cd /d "%~dp0"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\live_link.ps1" -Remove & echo. & pause & exit /b

:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
echo.
pause
endlocal
