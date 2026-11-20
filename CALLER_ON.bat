@echo off
rem Olympus: CALLER ON. Starts the AI caller's own server (127.0.0.1:8790, never the bot server's port) and its public address
rem (Tailscale Funnel :10000, so Twilio can reach it), points your Twilio number at it, then asks you to TYPE: START CALLING
rem and a daily cap. Consent-only: it dials ONLY businesses that signed the "Call me" form, landlines, weekdays 9-5 their time.
rem It never touches trading, NinjaTrader or the bot. Stop any time: CALLER_STOP.bat
setlocal EnableExtensions
title Olympus - CALLER ON
cd /d "%~dp0"
set "TS=tailscale"
where tailscale >nul 2>&1
if errorlevel 1 set "TS=%ProgramFiles%\Tailscale\tailscale.exe"
where python >nul 2>&1
if errorlevel 1 goto :nopy
if not exist "%USERPROFILE%\.olympus\caller.json" goto :nokeys
"%TS%" funnel --bg --yes --https=10000 http://127.0.0.1:8790
if errorlevel 1 goto :nots
for /f "usebackq delims=" %%U in (`python -X utf8 -m tools.caller.funnel address`) do set "PUB=%%U"
if "%PUB%"=="" goto :nots
python -X utf8 -m tools.caller.onoff on --public "%PUB%"
if errorlevel 1 goto :notstarted
python -X utf8 -m tools.caller.funnel hook "%PUB%"
start "Olympus caller" /min python -X utf8 -m tools.caller.server --public "%PUB%"
echo.
echo  [OK] AI caller is ON at %PUB%  (CALLER_STOP.bat turns it off)
echo.
pause
exit /b 0

:notstarted
"%TS%" funnel --https=10000 off >nul 2>&1
echo.
echo  Not started. Nothing was called.
pause
exit /b 1

:nokeys
echo  [FIX] No keys yet: run CALLER_SETUP.bat first.
pause
exit /b 1

:nots
echo  [FIX] Tailscale Funnel did not start. Open Tailscale, sign in, allow Funnel for this PC
echo        (admin console: Access controls, "funnel"), then run CALLER_ON.bat again.
pause
exit /b 1

:nopy
echo  [FIX] Python not found. Run ONE_TIME_SETUP.bat first.
pause
exit /b 1
