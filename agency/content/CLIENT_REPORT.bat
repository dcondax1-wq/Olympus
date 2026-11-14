@echo off
rem Monthly client report (docs\AGENCY_CONTENT.md): last month's one-page report + the email, for one client. Double-click.
rem It asks four things: the client id, the Google review count now and a month ago, and the form export (drag the CSV in).
rem Out: data\agency\reports\<client>\<month>\report.pdf (attach it), email.txt (paste it), report.html.
setlocal EnableExtensions
cd /d "%~dp0..\.."
where python >nul 2>&1
if errorlevel 1 goto :nopy
if not exist "data\agency\clients.json" goto :noclients
set "CID="
set "REV="
set "REVB="
set "LEADS="
set /p CID=  Client id (as in the client list):
if "%CID%"=="" goto :nocid
set /p REV=  Google reviews now (Enter to skip):
set /p REVB=  Google reviews a month ago (Enter to skip):
set /p LEADS=  Form export CSV - drag the file here (Enter to skip):
set "ARGS=--id "%CID%" --month last"
if not "%REV%"=="" set "ARGS=%ARGS% --reviews %REV%"
if not "%REVB%"=="" set "ARGS=%ARGS% --reviews-before %REVB%"
if not "%LEADS%"=="" set "ARGS=%ARGS% --leads %LEADS%"
python -X utf8 agency\content\client_report.py "data\agency\clients.json" %ARGS%
if errorlevel 1 goto :failed
echo.
echo  [OK] Done. Attach report.pdf and paste email.txt into your email to the client.
start "" explorer "data\agency\reports"
pause
exit /b 0

:failed
echo.
echo  [FIX] Something went wrong above. Send a photo of this window to Claude.
pause
exit /b 1

:nocid
echo  [FIX] No client id typed. Run it again.
pause
exit /b 1

:noclients
echo  [FIX] No client list yet: data\agency\clients.json (the agency CRM writes it).
pause
exit /b 1

:nopy
echo  [FIX] Python was not found. Send a photo of this window to Claude.
pause
exit /b 1
