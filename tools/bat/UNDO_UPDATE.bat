@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem Liquidity Engine: UNDO UPDATE (double-click). Puts back the files the last UPDATE_FROM_ZIP replaced and removes
rem the files it added (from backups\update_from_zip\). It refuses while the bot is running. Your local-only files
rem are not touched (a live_model*.json goes back only when that update gave it new values). It never
rem starts, stops or arms the bot. docs\NQ_BOT_BACK.md
setlocal EnableExtensions
rem the undo can remove or rewrite this very file: run from a copy in %TEMP% (see UPDATE_FROM_ZIP.bat)
if /i "%~1"=="--from-temp" goto :main
copy /y "%~f0" "%TEMP%\le_undo_update_run.bat" >nul 2>&1 || goto :main
call "%TEMP%\le_undo_update_run.bat" --from-temp "%LE_HOME%." & exit /b

:main
cd /d "%LE_HOME%"
if /i "%~1"=="--from-temp" cd /d "%~2"
title Liquidity Engine - UNDO UPDATE
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"

echo.
echo  ==== Liquidity Engine: UNDO UPDATE ====
echo.

"%PY%" --version >nul 2>&1
if errorlevel 1 goto :nopython
if not exist "%CD%\tools\update_from_zip.py" goto :notool
copy /y "%CD%\tools\update_from_zip.py" "%TEMP%\le_update_from_zip.py" >nul 2>&1
"%PY%" -X utf8 "%TEMP%\le_update_from_zip.py" --undo --folder "%CD%"
goto :end

:notool
echo  [OK] Nothing to undo: this folder has no tools\update_from_zip.py.
goto :end

:nopython
echo  [FIX] Python not found. Double-click ONE_TIME_SETUP.bat first. Nothing was changed.

:end
echo.
pause
endlocal
