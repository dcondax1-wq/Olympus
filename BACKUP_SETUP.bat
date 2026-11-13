@echo off
rem BACKUP SETUP: a second copy of the code on a free git host (Codeberg or GitLab) and a weekly zip in your synced folder.
rem It asks for the mirror address and the token (typed hidden, saved in %USERPROFILE%\.olympus, never in the bot folder),
rem installs the Sunday task OlympusWeeklyBackup and runs the backup once now. It never touches the bot or an order.
rem Undo: BACKUP_SETUP.bat -Remove (deletes the task only). docs\DISASTER_RECOVERY.md
setlocal EnableExtensions
title OLYMPUS - BACKUP SETUP
cd /d "%~dp0"
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" --version >nul 2>&1
if errorlevel 1 goto :nopython
if not exist "%~dp0tools\second_backup.py" goto :old
if /i "%~1"=="-Remove" goto :remove
"%PY%" -X utf8 "%~dp0tools\second_backup.py" --setup
if errorlevel 1 goto :end
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\backup_task.ps1"
echo.
echo  Running the backup once now (a few minutes) ...
"%PY%" -X utf8 "%~dp0tools\second_backup.py" --weekly
goto :end

:remove
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\backup_task.ps1" -Remove
goto :end

:old
echo  [FIX] tools\second_backup.py is missing: update the bot folder with UPDATE_FROM_ZIP.bat first.
goto :end

:nopython
echo  [FIX] Python not found. Install Python 3.12 from python.org and tick "Add python.exe to PATH".

:end
echo.
pause
endlocal
