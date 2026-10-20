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

echo.
echo  ==== Liquidity Engine: UPDATE ====
echo.

"%PY%" --version >nul 2>&1
if errorlevel 1 goto :nopython
git --version >nul 2>&1
if errorlevel 1 goto :nogit

rem ---- 1. never during a trade; ask first during trading time
"%PY%" -X utf8 -m engine.ops_checks --update-guard
set "GUARD=%errorlevel%"
if "%GUARD%"=="1" goto :intrade
if not "%GUARD%"=="2" goto :guardok
set "ANS="
set /p "ANS= Update anyway? Type Y then Enter: "
if /i not "%ANS%"=="Y" goto :notnow
:guardok

rem ---- 2. only the main branch
set "BR="
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "BR=%%b"
if /i not "%BR%"=="main" goto :notmain

rem ---- 3. stop the bot server (keeps the auto-resume record, so a Sim / paper bot comes back by itself)
echo  [..] Stopping the bot server
powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%scripts\stop_bot.ps1" -KeepAutostart

rem ---- 4. get the new code
echo  [..] Getting the new version (git pull)
git pull --ff-only origin main
if errorlevel 1 set "PULLFAIL=1"
if defined PULLFAIL echo  [FIX] git pull failed: the old version stays. Send this window to Claude.
if not defined PULLFAIL echo  [OK]  Code is up to date

rem ---- 5. packages
echo  [..] Installing packages (pip)
"%PY%" -m pip install -r requirements.txt --disable-pip-version-check -q
if errorlevel 1 echo  [FIX] pip install failed: check the internet, then run UPDATE again.
if not errorlevel 1 echo  [OK]  Packages installed

rem ---- 6. start the server again in its own window
echo  [..] Starting the bot server in its own window
start "Liquidity Engine bot" powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%scripts\run_bot.ps1"
"%PY%" -X utf8 -m engine.ops_checks --wait-server 120
if errorlevel 1 echo  [FIX] The server did not answer in 2 min: look at the "Liquidity Engine bot" window.

rem ---- 7. self-tests + health check
echo  [..] Self-tests and health check (about a minute)
"%PY%" -X utf8 -m engine.ops_checks --after-update
if errorlevel 1 goto :fixes
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

:notmain
echo  [FIX] The bot folder is on branch "%BR%", not main. Ask Claude to switch it to main.
goto :end

:nopython
echo  [FIX] Python not found. Install Python 3.12 from python.org and tick "Add python.exe to PATH".
goto :end

:nogit
echo  [FIX] Git not found. Install Git for Windows from git-scm.com.
goto :end

:end
echo.
pause
endlocal
