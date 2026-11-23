@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem Liquidity Engine: CLOUDFLARE SETUP (double-click). Moves the phone site to Cloudflare Pages (free, no badge) in one go:
rem installs Node.js if missing, asks for the Cloudflare key (hidden as you paste) and the Account ID, saves them in Windows
rem (never in a file, never shown), switches the publisher and publishes once, then shows the new address. Safe to run again.
rem It never starts, stops or arms the bot and never touches NinjaTrader or an order. docs\HOSTING.md
setlocal EnableExtensions
title Liquidity Engine - CLOUDFLARE SETUP
cd /d "%LE_HOME%"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
powershell -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\cloudflare_setup.ps1" %* & echo. & pause & exit /b

:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
echo.
pause
endlocal
