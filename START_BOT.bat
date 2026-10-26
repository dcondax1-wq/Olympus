@echo off
rem Zlarior + ATLAS: START BOT (double-click). One window does everything: update, set up both accounts once, the
rem Sim101 test once, then you type I ACCEPT LIVE RISK and the bot starts on the 50K and the 25K. Nothing real is armed
rem unless you type that line. Safe to double-click again: done steps are skipped; a running bot is left alone.
setlocal EnableExtensions
title Zlarior + ATLAS - START BOT
cd /d "%~dp0"
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" -X utf8 -m engine.go %*
echo.
pause
endlocal
