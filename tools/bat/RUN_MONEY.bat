@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem Liquidity Engine: MONEY ENGINE runner (paper only: it reads public data and writes JSON files, it never trades or touches the bot).
rem Double-click once to run it now. To run it every 30 minutes with Windows Task Scheduler (one line, run once in a normal Command Prompt):
rem   schtasks /Create /SC MINUTE /MO 30 /TN "LE Money Engine" /TR "\"C:\path\to\the bot folder\tools\bat\RUN_MONEY.bat\" auto" /F
rem Remove it again:  schtasks /Delete /TN "LE Money Engine" /F
rem "auto" = no pause at the end (for the scheduler). The result is in money_out\index.json; the Mint page shows it.
setlocal EnableExtensions
cd /d "%LE_HOME%"
where python >nul 2>&1
if errorlevel 1 goto :nopy
rem Your own bank / card exports (CSV / OFX / QFX you download yourself, dropped in %USERPROFILE%\.olympus\money_inbox\): a private ledger
rem outside this folder + money_out\household.json for the phone (private link only). Nothing logs in to a bank. docs\CONNECT_MONEY.md
python -X utf8 tools\money_import.py --out money_out --quiet >> money_out_log.txt 2>&1
python -X utf8 tools\money_engine.py --out money_out --timeout 60 >> money_out_log.txt 2>&1
rem Sibyl's own paper record (paper only). money_keep\sibyl_forward.json is the MEMORY (frozen start day): keep that folder, it is not synced anywhere.
if not exist money_keep mkdir money_keep
python -X utf8 tools\money\sibyl_results.py --state money_keep\sibyl_forward.json --out money_keep\sibyl_results.json >> money_out_log.txt 2>&1
python -X utf8 tools\money\sibyl_ledger.py --sibyl money_out\sibyl.json --state money_keep\sibyl_forward.json --results money_keep\sibyl_results.json >> money_out_log.txt 2>&1
if /I "%~1"=="auto" exit /b 0
type money_out_log.txt
echo.
echo  Done. Open the Mint page to see the five streams.
pause
exit /b 0

:nopy
echo  [FIX] Python was not found. Send a photo of this window to Claude.
if /I "%~1"=="auto" exit /b 1
pause
endlocal
