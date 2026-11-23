@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem KALSHI KEY SETUP (double-click, once). Saves your Kalshi API key on this PC OUTSIDE the bot folder:
rem   first on kalshi.com (on this PC): your account > Profile Settings > API Keys > Create New API Key (it downloads a .txt file),
rem   then this: it moves that file to your private folder (%USERPROFILE%\.olympus\kalshi), asks for the Key ID (hidden as you
rem   paste) and checks the key with one read of your balance. It never trades, never arms and never shows the key.
rem Going live is a separate step: KALSHI_LIVE.bat (you type the phrase). Work: scripts\kalshi_key_setup.ps1
setlocal EnableExtensions
title Kalshi - KEY SETUP
cd /d "%LE_HOME%"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
powershell -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\kalshi_key_setup.ps1" %* & echo. & pause & exit /b

:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
echo.
pause
endlocal
