@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem TEST ALERT (double-click): a fake 'TEST: Zlarior 50K LONG opened, 6 MNQ @ 21,555.50, stop 21,574.00, risk $228'
rem through EVERY channel (Telegram, Discord, ntfy, the Olympus app). Prints which delivered, with the receipt id. No trade.
setlocal EnableExtensions
title Olympus - TEST ALERT
cd /d "%LE_HOME%"
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" -X utf8 tools\alerts_setup.py test
echo.
pause
endlocal
