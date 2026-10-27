@echo off
rem Liquidity Engine: the "LE START" icon (double-click) and the Windows Startup folder at logon. Starts the bot server
rem first when it is not running, then opens the dashboard's Start page (one "Start trading" button does every step).
rem Starting the server never arms a real account. At logon the server may take a few minutes: it waits up to 5.
setlocal EnableExtensions
cd /d "%~dp0"
set "LEPORT=8766"
if defined PORT set "LEPORT=%PORT%"
set "URL=http://localhost:%LEPORT%/?page=start"

curl -s -f -m 3 -o nul "http://127.0.0.1:%LEPORT%/api/health/ping"
if not errorlevel 1 goto :open

echo  [..] The bot server is not running: starting it in its own window
start "Liquidity Engine bot" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0scripts\run_bot.ps1"
set /a N=0
:wait
timeout /t 2 /nobreak >nul
curl -s -f -m 2 -o nul "http://127.0.0.1:%LEPORT%/api/health/ping"
if not errorlevel 1 goto :open
set /a N+=1
if %N% lss 150 goto :wait
echo  [FIX] The server did not start in 5 minutes. Double-click HEALTH_CHECK.bat (the bot server runs hidden; its log is logs\server-YYYYMMDD.log).
pause
exit /b 1

:open
echo  [OK]  Opening %URL%
start "" "%URL%"
endlocal
