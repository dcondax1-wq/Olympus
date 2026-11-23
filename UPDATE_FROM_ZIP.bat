@echo off
rem Liquidity Engine: UPDATE FROM ZIP (double-click, or drag the code zip onto this file). The update without GitHub:
rem takes the newest OLYMPUS_BACKUP_*.zip from this folder, Downloads or Desktop, checks it (SHA-256 against the
rem .sha256.txt next to it), saves the files it will replace in backups\update_from_zip\ and updates the bot folder.
rem It REFUSES while the bot is running and asks first while the market is open. It never overwrites your local-only
rem files (alerts, TradingView, autostart, bot state, memory, .env, NinjaTrader bars, logs) and keeps a live_model*.json
rem you changed. It never starts, stops or arms the bot and never touches NinjaTrader or an order. Undo: tools\bat\UNDO_UPDATE.bat
rem docs\NQ_BOT_BACK.md step 1. The work is done by tools\update_from_zip.py.
setlocal EnableExtensions
rem cmd.exe reads a running .bat line by line from its byte offset, and the update below can rewrite this very file:
rem so it runs from a copy in %TEMP% (one line: call the copy, then exit; nothing here is read after the update).
if /i "%~1"=="--from-temp" goto :main
copy /y "%~f0" "%TEMP%\le_update_zip_run.bat" >nul 2>&1 || goto :main
call "%TEMP%\le_update_zip_run.bat" --from-temp "%~dp0." "%~1" "%~2" & exit /b

:main
cd /d "%~dp0"
set "A1=%~1"
set "A2=%~2"
if /i not "%~1"=="--from-temp" goto :args
cd /d "%~2"
set "A1=%~3"
set "A2=%~4"
:args
set "ARGS="
if not "%A1%"=="" set ARGS="%A1%"
if not "%A2%"=="" set ARGS=%ARGS% "%A2%"
title Liquidity Engine - UPDATE FROM ZIP
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"

echo.
echo  ==== Liquidity Engine: UPDATE FROM ZIP ====
echo.

"%PY%" --version >nul 2>&1
if errorlevel 1 goto :nopython

set "TOOL=%CD%\tools\update_from_zip.py"
if exist "%TOOL%" goto :run
rem the first time the old folder has no updater yet: take it out of the zip
set "TOOL=%TEMP%\le_update_from_zip.py"
"%PY%" -X utf8 -c "import glob,os,sys,zipfile as z;o,f=sys.argv[1:3];g=[a for a in sys.argv[3:] if a.lower().endswith('.zip')];h=os.path.expanduser('~');c=g or sorted(sum([glob.glob(os.path.join(d,'OLYMPUS_BACKUP_*.zip')) for d in (f,os.path.join(h,'Downloads'),os.path.join(h,'Desktop'))],[]),key=os.path.getmtime)[-1:];d=z.ZipFile(c[0]).read('tools/update_from_zip.py');open(o,'wb').write(d)" "%TOOL%" "%CD%" %ARGS%
if errorlevel 1 goto :nozip

:run
"%PY%" -X utf8 "%TOOL%" --folder "%CD%" --pip %ARGS%
if not "%errorlevel%"=="12" goto :end
echo.
set "ANS="
set /p "ANS= The bot is stopped. Update anyway while the market is open? Type Y then Enter: "
if /i not "%ANS%"=="Y" goto :notnow
"%PY%" -X utf8 "%TOOL%" --folder "%CD%" --pip --allow-market-open %ARGS%
goto :end

:notnow
echo.
echo  [OK] Nothing was changed. Run it again after 17:00 ET or at the weekend.
goto :end

:nozip
echo  [FIX] No code zip found (OLYMPUS_BACKUP_...zip). Download the zip to Downloads on this PC,
echo        or drag the zip onto UPDATE_FROM_ZIP.bat. Nothing was changed.
goto :end

:nopython
echo  [FIX] Python not found. Double-click tools\bat\ONE_TIME_SETUP.bat first. Nothing was changed.

:end
echo.
pause
endlocal
