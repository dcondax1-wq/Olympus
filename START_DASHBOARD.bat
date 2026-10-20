@echo off
rem Liquidity Engine: open the dashboard (double-click). Starts the bot server first when it is not running.
rem Starting the server never arms a real account.
setlocal EnableExtensions
cd /d "%~dp0"
set "LEPORT=8766"
if defined PORT set "LEPORT=%PORT%"
set "URL=http://localhost:%LEPORT%"

curl -s -f -m 3 -o nul "http://127.0.0.1:%LEPORT%/api/health/ping"
if not errorlevel 1 goto :open

echo  [..] The bot server is not running: starting it in its own window
start "Liquidity Engine bot" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_bot.ps1"
set /a N=0
:wait
timeout /t 2 /nobreak >nul
curl -s -f -m 2 -o nul "http://127.0.0.1:%LEPORT%/api/health/ping"
if not errorlevel 1 goto :open
set /a N+=1
if %N% lss 60 goto :wait
echo  [FIX] The server did not start in 2 minutes. Look at the "Liquidity Engine bot" window, or double-click HEALTH_CHECK.
pause
exit /b 1

:open
echo  [OK]  Opening %URL%
start "" "%URL%"
endlocal
