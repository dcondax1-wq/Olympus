@echo off
rem Liquidity Engine: update the bot (double-click). Stops the bot server, pulls main, installs packages, starts the
rem server again in its own window, runs the self-tests and the health check. It never arms or starts a real account:
rem a Sim / paper bot resumes by itself; the eval bot resumes only if you turned auto-resume on yourself.
setlocal EnableExtensions
rem cmd.exe reads a running .bat line by line from its byte offset, and the pull below can rewrite this very file:
rem so the update runs from a copy in %TEMP% (one line: call the copy, then exit; nothing here is read after the pull).
if /i "%~1"=="--from-temp" goto :main
copy /y "%~f0" "%TEMP%\le_update_run.bat" >nul 2>&1 || goto :main
call "%TEMP%\le_update_run.bat" --from-temp "%~dp0." & exit /b

:main
cd /d "%~dp0"
if /i "%~1"=="--from-temp" cd /d "%~2"
set "HERE=%CD%\"
title Liquidity Engine - UPDATE
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
set "PULLFAIL="
rem exit code for MONDAY_SETUP (engine/monday.py): 0 done / waits by design, 1 not updated, 2 updated but red lines
set "RC=0"

echo.
echo  ==== Liquidity Engine: UPDATE ====
echo.

"%PY%" --version >nul 2>&1
if errorlevel 1 goto :nopython

rem ---- 1. never during a trade; ask first during trading time
"%PY%" -X utf8 -m engine.ops_checks --update-guard
set "GUARD=%errorlevel%"
if "%GUARD%"=="1" goto :intrade
if not "%GUARD%"=="2" goto :guardok
set "ANS="
set /p "ANS= Update anyway? Type Y then Enter: "
if /i not "%ANS%"=="Y" goto :notnow
:guardok

rem ---- 2. only the main branch: checked by step 4 (engine.autoupdate --pull finds git itself, also off PATH)

rem ---- 3. stop the bot server (keeps the auto-resume record, so a Sim / paper bot comes back by itself)
echo  [..] Stopping the bot server
powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%scripts\stop_bot.ps1" -KeepAutostart

rem ---- 4. get the new code: the auto-update's own fast-forward of main (engine/autoupdate.py --pull). Before it:
rem ATLAS's account block goes from second_model.json to data\account_b.json, bot-made files (cache/dash, GEX/VIX,
rem check reports) and files checked out from main by hand go back to HEAD, a shallow history is deepened. A file
rem changed by hand still blocks it.
echo  [..] Getting the new version
"%PY%" -X utf8 -m engine.autoupdate --pull
if errorlevel 1 set "PULLFAIL=1"
if defined PULLFAIL set "RC=1"
if defined PULLFAIL echo  [FIX] The update did not go through: the old version stays. Send this window to Claude.
if not defined PULLFAIL echo  [OK]  Code is up to date

rem ---- 5. packages
echo  [..] Installing packages (pip)
"%PY%" -m pip install -r requirements.txt --disable-pip-version-check -q
if errorlevel 1 echo  [FIX] pip install failed: check the internet, then run UPDATE again.
if not errorlevel 1 echo  [OK]  Packages installed

rem ---- 6. start the server again in its own window
echo  [..] Starting the bot server in its own window
start "Liquidity Engine bot" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%HERE%scripts\run_bot.ps1"
"%PY%" -X utf8 -m engine.ops_checks --wait-server 120
if errorlevel 1 echo  [FIX] The server did not answer in 2 min: double-click HEALTH_CHECK.bat (the server runs hidden; log in logs\server-YYYYMMDD.log).

rem ---- 7. self-tests + health check
echo  [..] Self-tests and health check (about a minute)
"%PY%" -X utf8 -m engine.ops_checks --after-update
if errorlevel 1 goto :fixes
if "%RC%"=="0" set "RC=2"
echo.
echo  [OK]  UPDATE done. All green.
goto :end

:fixes
echo.
echo  [FIX] UPDATE done, but the red lines above need a fix.
goto :end

:intrade
echo  [FIX] Not updating now: a trade or a setup is open. Run UPDATE after it closes.
goto :end

:notnow
echo  Not updated. Best time: after 16:00 ET.
goto :end

:nopython
set "RC=1"
echo  [FIX] Python not found. Install Python 3.12 from python.org and tick "Add python.exe to PATH".
goto :end

:end
echo.
pause
endlocal & exit /b %RC%
