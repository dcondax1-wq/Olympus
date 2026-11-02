@echo off
rem NO CHART MODE: copies the LE_Feed add-on into NinjaTrader so the bot gets its bars with no chart open.
rem Then press F5 once in NinjaTrader's NinjaScript Editor. Steps: ninjatrader\SETUP.md "No-chart mode".
setlocal EnableExtensions
title Zlarior + ATLAS - NO CHART MODE
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\no_chart_mode.ps1" & echo. & pause & exit /b
