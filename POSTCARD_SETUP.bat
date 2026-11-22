@echo off
rem POSTCARD SETUP (double-click, once). Personalised postcards to businesses with a built concept site: "<Business>, your new website is
rem already built - scan to see it". Installs the two free libraries it needs (Pillow, segno), asks for your Lob API key (hidden),
rem your name, business, the email for "no more mail" and your return address (a P.O. box: your step), then the phrase gate: type
rem SEND POSTCARDS to mail real cards (max 20 a day, 100 a week, a live_ key, real postage about $0.91 a card); anything else = TEST mode
rem (a test_ key: nothing printed, mailed or charged). Saves to %%USERPROFILE%%\.olympus. Never touches the trading bot. Off: POSTCARD_STOP.bat
setlocal EnableExtensions
title Agency - POSTCARD SETUP
cd /d "%~dp0"
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" -m pip install --user --quiet segno pillow
"%PY%" -X utf8 tools\postcards.py setup
if errorlevel 1 goto :end
"%PY%" -X utf8 tools\postcards.py samples --out "%USERPROFILE%\.olympus\postcard_samples"
echo  Sample cards: %USERPROFILE%\.olympus\postcard_samples (open sample-cards.pdf)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\agency_mail_task.ps1"
"%PY%" -X utf8 tools\postcards.py status
:end
echo.
pause
endlocal
