@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem Liquidity Engine: PC DOCTOR (double-click). Why the phone hears nothing from this PC: the bot server, its heartbeat,
rem GitHub-free mode, the 15-minute report task (OlympusPCReport), the report's last run, your ntfy alert topic, ntfy.sh, and
rem the auto-update connect, one line each, then the MOST LIKELY CAUSE and the one line to copy. It only looks: nothing is
rem started, stopped, armed, installed or sent. tools\pc_doctor.py, docs\PC_DOCTOR.md
setlocal EnableExtensions
title Liquidity Engine - PC DOCTOR
cd /d "%LE_HOME%"
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" --version >nul 2>&1
if errorlevel 1 goto :nopython
"%PY%" -X utf8 tools\pc_doctor.py %*
goto :end

:nopython
echo  [FIX] Python not found. Install Python 3.12 from python.org and tick "Add python.exe to PATH".

:end
echo.
pause
endlocal
