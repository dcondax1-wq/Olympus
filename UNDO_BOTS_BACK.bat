@echo off
rem Liquidity Engine: UNDO BOTS BACK (double-click). Removes the 15-minute phone report task, the GitHub-free mode file (only if
rem BOTS_BACK.bat made it) and the git sign-in setting it made. The bot itself is not stopped or changed. docs\BOTS_BACK.md
setlocal EnableExtensions
title Liquidity Engine - UNDO BOTS BACK
cd /d "%~dp0"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bots_back.ps1" -Remove & echo. & pause & exit /b

:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
echo.
pause
endlocal
