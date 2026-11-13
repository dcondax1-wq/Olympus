@echo off
rem Zlarior + ATLAS: GO LIVE ON THE EVAL (owner 2026-11-12: "Zlarior and ATLAS trading on my eval tonight").
rem One double-click, two parts in one window:
rem   1. BOTS BACK without resuming paper (scripts\bots_back.ps1 -NoResume): GitHub pushes off, NinjaTrader and its LE_BarFeed bars
rem      checked, the bot server up, the phone reports (ntfy) installed, six status lines.
rem   2. START BOT (python -m engine.go, the same as START_BOT.bat): both accounts, the Sim test once, then YOU type
rem      I ACCEPT LIVE RISK to arm the eval. Claude never types it and this file never arms anything by itself.
rem Safe to double-click again: done steps are skipped, a running bot is left alone. Stop: STOP_BOT.bat. docs\TONIGHT_EVAL.md.
setlocal EnableExtensions
title Zlarior + ATLAS - GO LIVE ON THE EVAL
cd /d "%~dp0"
if not exist "%~dp0scripts\bots_back.ps1" goto :old
echo.
echo  ===== Part 1 of 2: bots back without GitHub =====
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bots_back.ps1" -NoResume
echo.
echo  ===== Part 2 of 2: START BOT (you type the live phrase yourself) =====
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" -X utf8 -m engine.go %*
echo.
pause
endlocal
exit /b

:old
echo  [FIX] This bot folder has old code. Put the new code zip in Downloads and double-click UPDATE_FROM_ZIP.bat first,
echo        then double-click GO_LIVE_EVAL.bat again. Nothing was changed.
echo.
pause
exit /b
