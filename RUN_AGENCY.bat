@echo off
rem OLYMPUS AGENCY: the website machine (docs\AGENCY.md). Double-click: it finds today's leads, builds 3 demo sites,
rem writes each one's pitch kit and refreshes the Agency page. It never sends an email or calls anyone: you do that.
rem First run: it makes agency\config.json (your agency name, phone, email, postal address, city, prices) and opens it.
rem Another city for one run:  RUN_AGENCY.bat --city "Boise, ID"
setlocal EnableExtensions
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 goto :nopy
if not exist "agency\config.json" goto :first
python -X utf8 -m agency.run %*
if errorlevel 2 goto :fix
echo.
echo  Done. In the folder that opens: drag each "site" folder onto app.netlify.com/drop, press Publish,
echo  then open the Agency page on your phone and call the top leads.
start "" explorer "agency\out"
pause
exit /b 0

:first
copy /y "agency\config.example.json" "agency\config.json" >nul
echo  First run. Notepad opens your settings file now: replace every YOUR ... word
echo  (agency name, your name, phone, email, postal address, your city), save, close Notepad,
echo  then double-click RUN_AGENCY.bat again.
start "" notepad "agency\config.json"
pause
exit /b 0

:fix
echo  [FIX] The lead finder stopped: read the [STOP] line above. Usually the city in agency\config.json
echo  needs its state ("Boise, ID"), or the free map server is busy: try again in an hour.
pause
exit /b 2

:nopy
echo  [FIX] Python was not found. Send a photo of this window to Claude.
pause
endlocal
