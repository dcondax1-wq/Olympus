@echo off
rem ROLL: the quarterly contract switch in one double-click (next: Wed Dec 9 2026 after 16:00 ET, MNQ 12-26 -> MNQ 03-27).
rem It waits until every bot is flat, removes an old pinned contract, tells you the one NinjaTrader click and checks it.
rem It never places or changes an order and never arms anything. docs\ROLL_DEC_2026.md
setlocal EnableExtensions
title Zlarior + ATLAS - ROLL
cd /d "%~dp0"
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" --version >nul 2>&1
if errorlevel 1 goto :nopython
if not exist "%~dp0tools\roll_now.py" goto :old
"%PY%" -X utf8 "%~dp0tools\roll_now.py" %*
goto :end

:old
echo  [FIX] tools\roll_now.py is missing: update the bot folder with UPDATE_FROM_ZIP.bat first.
goto :end

:nopython
echo  [FIX] Python not found. Install Python 3.12 from python.org and tick "Add python.exe to PATH".

:end
echo.
pause
endlocal
