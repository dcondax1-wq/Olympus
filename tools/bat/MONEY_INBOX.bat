@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem Liquidity Engine: MONEY INBOX for the iPhone Shortcut (docs\CONNECT_MONEY.md). Double-click once.
rem A tiny SEPARATE server that only appends a cash entry (or a balance) to %USERPROFILE%\.olympus\money_inbox\cash.jsonl.
rem It never trades and is not the bot server. It listens on this PC only (127.0.0.1:8767); Tailscale makes it
rem https://<this-pc>.<tailnet>.ts.net:8443/inbox for YOUR devices only (tailscale serve, never Funnel).
rem It starts now and at every sign-in (Task Scheduler task "OlympusMoneyInbox"). Undo:  MONEY_INBOX.bat off
setlocal EnableExtensions
title Liquidity Engine - MONEY INBOX
cd /d "%LE_HOME%"
set "TS=tailscale"
where tailscale >nul 2>&1
if errorlevel 1 set "TS=%ProgramFiles%\Tailscale\tailscale.exe"
if /I "%~1"=="off" goto :off
where python >nul 2>&1
if errorlevel 1 goto :nopy
if /I "%~1"=="run" goto :run
schtasks /Create /SC ONLOGON /TN "OlympusMoneyInbox" /TR "\"%~f0\" run" /F >nul 2>&1
call :start
if not exist "%TS%" if /I not "%TS%"=="tailscale" goto :nots
"%TS%" serve --bg --yes --https=8443 http://127.0.0.1:8767
if errorlevel 1 goto :nots
echo.
echo  [OK] Money inbox is on. On the iPhone, the Shortcut posts to:
echo       https://YOUR-PC.YOUR-TAILNET.ts.net:8443/inbox
echo       (the same address as your live link, with :8443/inbox at the end)
echo.
pause
exit /b 0

:run
call :start
exit /b 0

:start
where pythonw >nul 2>&1
if errorlevel 1 (start "Money inbox" /min python -X utf8 tools\money_inbox_server.py) else (start "" pythonw -X utf8 tools\money_inbox_server.py)
exit /b 0

:off
schtasks /Delete /TN "OlympusMoneyInbox" /F >nul 2>&1
"%TS%" serve --https=8443 off >nul 2>&1
echo  [OK] Money inbox task removed and the :8443 link turned off. Close its window (or sign out) to stop the server now.
echo.
pause
exit /b 0

:nots
echo  [FIX] Tailscale did not answer. Run LIVE_LINK.bat first (it sets Tailscale up), then MONEY_INBOX.bat again.
echo        The inbox itself is running on this PC.
echo.
pause
exit /b 1

:nopy
echo  [FIX] Python was not found. Send a photo of this window to Claude.
echo.
pause
endlocal
