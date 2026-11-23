@echo off
rem MONDAY SETUP (owner 2026-11-22): the ONE weekly double-click. In order, one line each: the update (UPDATE.bat),
rem the clock fix once (Windows asks Yes for administrator for that part only), START BOT (you type I ACCEPT LIVE RISK
rem yourself: it arms every account AND turns the 7-day keep-alive on for them), then the alert test. Safe to run twice.
rem Double-click it normally (NOT Run as administrator: the bot must never run elevated). Uses engine/monday.py.
setlocal EnableExtensions
rem the update below can rewrite this very file while cmd.exe reads it: run from a copy in %TEMP% (as UPDATE.bat does)
if /i "%~1"=="--from-temp" goto :main
copy /y "%~f0" "%TEMP%\le_monday_run.bat" >nul 2>&1 || goto :main
call "%TEMP%\le_monday_run.bat" --from-temp "%~dp0." & exit /b

:main
cd /d "%~dp0"
if /i "%~1"=="--from-temp" cd /d "%~2"
title Olympus - MONDAY SETUP
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" --version >nul 2>&1
if errorlevel 1 goto :nopython
"%PY%" -X utf8 -m engine.monday
goto :end
:nopython
echo  [FIX] Python not found. Install Python 3.12 from python.org and tick "Add python.exe to PATH".
:end
echo.
pause
endlocal
