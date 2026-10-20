@echo off
rem Liquidity Engine: one screen of green / yellow / red checks, each red line with its one fix (double-click).
rem Read-only: it never starts, stops or changes anything.
setlocal EnableExtensions
title Liquidity Engine - HEALTH CHECK
cd /d "%~dp0"
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" --version >nul 2>&1
if errorlevel 1 goto :nopython
"%PY%" -X utf8 -m engine.ops_checks
goto :end

:nopython
echo  [FIX] Python not found. Install Python 3.12 from python.org and tick "Add python.exe to PATH".

:end
echo.
pause
endlocal
