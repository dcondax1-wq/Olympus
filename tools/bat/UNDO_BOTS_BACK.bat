@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem Liquidity Engine: UNDO BOTS BACK (double-click). Removes the 15-minute phone report task, the GitHub-free mode file (only if
rem BOTS_BACK.bat made it) and the git sign-in setting it made. The bot itself is not stopped or changed. docs\BOTS_BACK.md
setlocal EnableExtensions
title Liquidity Engine - UNDO BOTS BACK
cd /d "%LE_HOME%"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
powershell -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\bots_back.ps1" -Remove & echo. & pause & exit /b

:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
echo.
pause
endlocal
