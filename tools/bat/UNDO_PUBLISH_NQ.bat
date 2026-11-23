@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem Liquidity Engine: UNDO PUBLISH NQ (double-click). Removes the 15-minute publish task and switches the bot's GitHub-free mode
rem off again (applies at the bot's next start). Your Netlify / folder settings stay. Nothing else is touched. docs\NQ_BOT_BACK.md
setlocal EnableExtensions
title Liquidity Engine - UNDO PUBLISH NQ
cd /d "%LE_HOME%"
where powershell >nul 2>&1
if errorlevel 1 goto :nops
powershell -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\publish_nq.ps1" -Remove & echo. & pause & exit /b

:nops
echo  [FIX] Windows PowerShell not found. Send a photo of this window to Claude.
echo.
pause
endlocal
