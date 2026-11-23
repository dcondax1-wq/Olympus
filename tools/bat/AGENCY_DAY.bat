@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem OLYMPUS AGENCY DAY (docs\BUSINESS.md): ONE double-click for the whole agency day. It finds today's leads in your city,
rem builds 3 demo sites with their pitch kits, makes the call list for the phone, refreshes the Business page and writes
rem agency\out\TODAY.txt (who to call, the opener, the price, the rules). It never sends an email, a text or calls anyone: you do.
rem First run: it makes agency\config.json (your agency name, phone, email, postal address, city, prices) and opens it.
rem Another city for one run:  AGENCY_DAY.bat --city "Boise, ID"
setlocal EnableExtensions
cd /d "%LE_HOME%"
where python >nul 2>&1
if errorlevel 1 goto :nopy
if not exist "agency\config.json" goto :first
python -X utf8 -m agency.day %*
if errorlevel 2 goto :fix
echo.
echo  Done. 1) Drag each "site" folder onto app.netlify.com/drop, press Publish.
echo  2) Open the Agency page on your phone (Call today).  3) Call by hand, in business hours.
if exist "agency\out\TODAY.txt" start "" notepad "agency\out\TODAY.txt"
start "" explorer "agency\out"
pause
exit /b 0

:first
copy /y "agency\config.example.json" "agency\config.json" >nul
echo  First run. Notepad opens your settings file now: replace every YOUR ... word
echo  (agency name, your name, phone, email, postal address, your city), save, close Notepad,
echo  then double-click AGENCY_DAY.bat again.
start "" notepad "agency\config.json"
pause
exit /b 0

:fix
echo  [FIX] The agency day stopped: read the [STOP] line above. Usually the city in agency\config.json
echo  needs its state ("Boise, ID"), or the free map server is busy: try again in an hour.
pause
exit /b 2

:nopy
echo  [FIX] Python was not found. Send a photo of this window to Claude.
pause
endlocal
