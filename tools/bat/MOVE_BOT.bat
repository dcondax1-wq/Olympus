@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem Liquidity Engine: MOVE THE BOT to another PC (double-click). 1 = pack and retire this PC (the old one, after 4:05 PM ET);
rem 2 = set this PC up (the new one, from the BOT_MOVE folder in OneDrive); 3 = no old PC: start fresh here (no pack). Two PCs never trade the same accounts.
rem What it does: scripts\move_bot.ps1 (top of the file).
setlocal EnableExtensions
title Liquidity Engine - MOVE THE BOT
cd /d "%LE_HOME%"
set "S=%LE_HOME%scripts\move_bot.ps1"
if not exist "%S%" set "S=%LE_HOME%move_bot.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%S%" & echo. & pause & exit /b
