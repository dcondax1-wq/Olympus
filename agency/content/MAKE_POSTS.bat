@echo off
rem Agency content machine: next month's social posts for every paying client (docs\AGENCY_CONTENT.md). Double-click.
rem One client:  MAKE_POSTS.bat fade-co       One client and a month:  MAKE_POSTS.bat fade-co 2027-01
rem Reads the client list data\agency\clients.json. Draws the images with Microsoft Edge (already on Windows): nothing to install.
rem The posts land in data\agency\content\<client>\<month>\ (contact_sheet.html, posts\, posts.csv, client_message.txt).
setlocal EnableExtensions
cd /d "%~dp0..\.."
where python >nul 2>&1
if errorlevel 1 goto :nopy
if not exist "data\agency\clients.json" goto :noclients
set "MONTH=%~2"
if "%MONTH%"=="" set "MONTH=next"
if "%~1"=="" goto :all
python -X utf8 agency\content\make_posts.py "data\agency\clients.json" --id "%~1" --month %MONTH%
goto :done

:all
python -X utf8 agency\content\make_posts.py "data\agency\clients.json" --all --month %MONTH%

:done
if errorlevel 1 goto :failed
echo.
echo  [OK] Done. Next: send each client contact_sheet.png + client_message.txt from its folder.
start "" explorer "data\agency\content"
pause
exit /b 0

:failed
echo.
echo  [FIX] Something went wrong above. Send a photo of this window to Claude.
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
