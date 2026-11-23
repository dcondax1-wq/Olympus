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
"%PY%" --version >nul 2>&1
if errorlevel 1 goto :nopython
"%PY%" -X utf8 -m engine.go %*
if errorlevel 1 echo  [FIX] START BOT stopped before the end: do the first [FIX] line above, then double-click START_BOT.bat again.
goto :end
:nopython
echo  [FIX] Python not found. Install Python 3.12 from python.org and tick "Add python.exe to PATH".
:end
echo.
pause
endlocal
