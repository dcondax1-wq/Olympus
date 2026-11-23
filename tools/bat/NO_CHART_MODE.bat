@echo off
set "LE_HOME=%~dp0"
if not exist "%~dp0engine\" if exist "%~dp0..\..\engine\" for %%I in ("%~dp0..\..") do set "LE_HOME=%%~fI\"
rem NO CHART MODE: copies the LE_Feed add-on into NinjaTrader so the bot gets its bars with no chart open.
rem Then press F5 once in NinjaTrader's NinjaScript Editor. Steps: ninjatrader\SETUP.md "No-chart mode".
setlocal EnableExtensions
title Zlarior + ATLAS - NO CHART MODE
cd /d "%LE_HOME%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\no_chart_mode.ps1" & echo. & pause & exit /b
