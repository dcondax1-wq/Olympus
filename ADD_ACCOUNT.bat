@echo off
rem Add a new MFFU account to the bot (double-click). It only ADDS the account, disarmed: nothing trades until you
rem press START BOT and type the live phrase yourself. Uses engine/account_cli.py and engine/lit25.py.
setlocal EnableExtensions
cd /d "%~dp0"
title Liquidity Engine - ADD ACCOUNT
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
echo.
echo  ==== Add an account ====
echo   1  New Builder 25K eval      (Zlarior trades it)
echo   2  New Builder 50K eval      (Zlarior trades it)
echo   3  New Rapid EOD 50K eval    (Zlarior + ATLAS)
echo   4  ATLAS's FUNDED 25K        (after MFFU's Upgrade)
echo.
set "CH="
set /p CH=Type 1, 2, 3 or 4 and press Enter: 
set "NAME="
echo.
echo  Copy the account's Name from NinjaTrader (Accounts tab) and paste it here.
set /p NAME=Account name: 
if "%NAME%"=="" goto :noname
if "%CH%"=="1" "%PY%" -X utf8 -m engine.accounts add --plan builder25k --name "%NAME%" & goto :done
if "%CH%"=="2" "%PY%" -X utf8 -m engine.accounts add --plan builder50k --name "%NAME%" & goto :done
if "%CH%"=="3" "%PY%" -X utf8 -m engine.accounts add --plan rapideod --name "%NAME%" & goto :done
if "%CH%"=="4" for /f %%d in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyy-MM-dd')"') do "%PY%" -X utf8 -m engine.lit25 --funded "%NAME%" --start %%d & goto :done
echo  [FIX] Type only 1, 2, 3 or 4. Nothing changed.
goto :end
:noname
echo  [FIX] No name pasted. Nothing changed.
goto :end
:done
echo.
echo  Done. Next: STOP BOT (if it runs), then START BOT and type the live phrase yourself.
:end
echo.
pause
