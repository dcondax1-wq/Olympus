@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem GitHub sign-in for the PRIVATE backup (owner 2026-11-19). One double-click: if a GitHub window opens, sign in as
rem dcondax1-wq. Fetch only: it never touches the bot, its files or any order. Safe while the bot runs.
cd /d "%LE_HOME%"
title Liquidity Engine - GitHub sign-in
set "PY=python"
if defined LE_PYTHON set "PY=%LE_PYTHON%"
set "PYTHONIOENCODING=utf-8"
"%PY%" -X utf8 -m engine.autoupdate --signin
echo.
pause
