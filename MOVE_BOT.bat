@echo off
rem Liquidity Engine: MOVE THE BOT to another PC (double-click). 1 = pack and retire this PC (the old one, after 4:05 PM ET);
rem 2 = set this PC up (the new one, from the BOT_MOVE folder in OneDrive). Two PCs never trade the same accounts.
rem What it does: scripts\move_bot.ps1 (top of the file).
setlocal EnableExtensions
title Liquidity Engine - MOVE THE BOT
cd /d "%~dp0"
set "S=%~dp0scripts\move_bot.ps1"
if not exist "%S%" set "S=%~dp0move_bot.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%S%" & echo. & pause & exit /b
