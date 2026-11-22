@echo off
rem Add a new MFFU account to the bot (double-click). It only ADDS the account, disarmed: nothing trades until you
rem press START BOT and type the live phrase yourself. Uses engine/account_cli.py and engine/lit25.py.
rem First it prints what it detected (engine/onboard.py: plan from the Name, 25K / 50K from the balance, passed or fresh).
rem A refused add (wrong Name, wrong size, one Rapid only) says [NOT ADDED] and never "Done ... START BOT" (night-money 2026-11-18).
setlocal EnableExtensions
cd /d "%~dp0"
title Liquidity Engine - ADD ACCOUNT
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
echo.
echo  ==== What NinjaTrader shows ====
"%PY%" -X utf8 -m engine.onboard
echo  (Easiest: type it on the page http://localhost:8766/add-account/ - on the PC, or your Tailscale link + /add-account/ on the phone.)
echo.
echo  ==== Add an account ====
echo   1  New Builder 25K eval      $63 (one was $43)  - Zlarior trades it
echo   2  New Builder 50K eval      $91.80  - Zlarior trades it
echo   3  New Rapid EOD 50K eval    $165 (CLUB)  - Zlarior + ATLAS
echo   4  ATLAS's FUNDED 25K        no new buy  - after MFFU's Upgrade
echo   5  New Rapid EOD 25K eval    $97.20 (CLUB)  - Zlarior + ATLAS
echo   (FundedNext and Lucid are OFF: they need a written yes first. Easier: TRADE_HOME.bat, choice 4.)
echo.
set "CH="
set /p CH=Type 1, 2, 3, 4 or 5 and press Enter: 
set "NAME="
echo.
echo  Copy the account's Name from NinjaTrader (Accounts tab) and paste it here.
set /p NAME=Account name: 
if "%NAME%"=="" goto :noname
if "%CH%"=="1" "%PY%" -X utf8 -m engine.accounts add --plan builder25k --name "%NAME%" && goto :done || goto :notadded
if "%CH%"=="2" "%PY%" -X utf8 -m engine.accounts add --plan builder50k --name "%NAME%" && goto :done || goto :notadded
if "%CH%"=="3" "%PY%" -X utf8 -m engine.accounts add --plan rapideod --name "%NAME%" && goto :done || goto :notadded
if "%CH%"=="5" "%PY%" -X utf8 -m engine.accounts add --plan rapideod25 --name "%NAME%" && goto :done || goto :notadded
if "%CH%"=="4" for /f %%d in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyy-MM-dd')"') do "%PY%" -X utf8 -m engine.lit25 --funded "%NAME%" --start %%d && goto :done || goto :notadded
echo  [FIX] Type only 1, 2, 3, 4 or 5. Nothing changed.
goto :end
:noname
echo  [FIX] No name pasted. Nothing changed.
goto :end
:notadded
echo.
echo  [NOT ADDED] Read the line above: nothing changed, the bot keeps trading as before. No restart needed.
echo  Fix the Name (copy it again from NinjaTrader, Accounts tab) and run ADD_ACCOUNT.bat again.
goto :end
:done
echo.
echo  Added HELD (not armed). Next: STOP BOT if it runs, then START BOT and type the live phrase yourself. Nothing trades until then.
:end
echo.
pause
