@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem RESTORE ON A NEW PC (day-ops2): after SETUP_EVERYTHING.bat on the new PC, this puts back your accounts, switches and alert
rem set-up from the weekly encrypted backup (engine/pc_backup.py). It asks for the backup file (Enter = the newest in
rem OneDrive\Olympus Backup) and your recovery code. Nothing is armed: START_BOT.bat + your phrase afterwards.
setlocal EnableExtensions
title Olympus - RESTORE ON A NEW PC
cd /d "%LE_HOME%"
set "PY=%LE_HOME%.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -X utf8 -m engine.pc_backup --restore-newest
echo.
pause
endlocal
