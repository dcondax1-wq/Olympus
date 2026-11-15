@echo off
rem Agency content machine: next month's social posts for every paying client with social posts (docs\AGENCY_CONTENT.md). Double-click.
rem One client:  MAKE_POSTS.bat fade-co       One client and a month:  MAKE_POSTS.bat fade-co 2027-01
rem Reads the client list the CRM saved (data\agency\clients.json, crm.json or leads.json). Draws the images with Microsoft Edge
rem (already on Windows): nothing to install. The posts land in data\agency\content\<client>\<month>\.
setlocal EnableExtensions
cd /d "%~dp0..\.."
where python >nul 2>&1
if errorlevel 1 goto :nopy
set "MONTH=%~2"
if "%MONTH%"=="" set "MONTH=next"
if "%~1"=="" goto :all
python -X utf8 agency\content\make_posts.py --id "%~1" --month %MONTH%
goto :done

:all
python -X utf8 agency\content\make_posts.py --all --month %MONTH%

:done
if errorlevel 1 goto :failed
echo.
echo  [OK] Done. Next: send each client contact_sheet.png + client_message.txt from its folder.
start "" explorer "data\agency\content"
pause
exit /b 0

:failed
echo.
echo  [FIX] Nothing was made: read the line above. Send a photo of this window to Claude if it is not clear.
pause
exit /b 1

:nopy
echo  [FIX] Python was not found. Send a photo of this window to Claude.
pause
exit /b 1
