@echo off
rem OLYMPUS: SETUP EVERYTHING (double-click; owner 2026-11-14: "one double-click"). ONE window walks you through this
rem weekend's three PC jobs in order; each one is checked first and skipped when it is already done:
rem   1 NEW CODE    the newest OLYMPUS_BACKUP_*.zip (+ its .sha256.txt) from Downloads / the Desktop into the bot folder
rem   2 PHONE LINK  the private Tailscale link to the dashboard, shown big and put on the clipboard
rem   3 GO LIVE     only after you type YES (Sunday after 6 PM ET, both evals active on MFFU): GO_LIVE_EVAL's flow, where
rem                 YOU type the live phrase yourself. This file never types it, never stores it and never arms anything.
rem It also works double-clicked inside the zip: it finds the bot folder by itself. The work is done by
rem scripts\setup_everything.ps1 (taken out of the newest code zip when only this file is here). docs\SETUP_EVERYTHING.md
setlocal EnableExtensions
rem cmd.exe reads a running .bat line by line from its byte offset and the update below can rewrite this very file:
rem so it runs from a copy in %TEMP% (one line: call the copy, then exit; nothing here is read after the update).
if /i "%~1"=="--from-temp" goto :main
copy /y "%~f0" "%TEMP%\le_setup_everything_run.bat" >nul 2>&1 || goto :main
call "%TEMP%\le_setup_everything_run.bat" --from-temp "%~dp0." "%~1" & exit /b

:main
set "HERE=%~dp0."
set "A1=%~1"
if /i not "%~1"=="--from-temp" goto :args
set "HERE=%~2"
set "A1=%~3"
:args
title OLYMPUS - SETUP EVERYTHING
where powershell >nul 2>&1
if errorlevel 1 goto :nops
set "PS1=%HERE%\scripts\setup_everything.ps1"
if exist "%PS1%" goto :run
rem only this file is here (double-clicked inside the zip, or copied alone): take the script out of the newest code zip
set "PS1=%TEMP%\le_setup_everything.ps1"
set "LE_SE_ZIP=%A1%"
set "LE_SE_HERE=%HERE%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $o=Join-Path $env:TEMP 'le_setup_everything.ps1'; $z=$env:LE_SE_ZIP; if (-not $z) { $h=$env:USERPROFILE; $c=@(); $dl=$null; try { $dl=(New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path } catch { }; foreach ($d in @($env:LE_SE_HERE, $dl, (Join-Path $h 'Downloads'), (Join-Path $h 'Desktop'), (Join-Path $h 'OneDrive\Downloads'), (Join-Path $h 'OneDrive\Desktop'), [Environment]::GetFolderPath('Desktop'))) { if ($d -and (Test-Path -LiteralPath $d)) { $c += @(Get-ChildItem -LiteralPath $d -Filter 'OLYMPUS_BACKUP_*.zip' -File -ErrorAction SilentlyContinue) } }; if (-not $c.Count) { exit 2 }; $z=($c | Sort-Object LastWriteTime | Select-Object -Last 1).FullName }; try { Add-Type -AssemblyName System.IO.Compression.FileSystem } catch { }; $a=[IO.Compression.ZipFile]::OpenRead($z); $e=$a.GetEntry('scripts/setup_everything.ps1'); if ($e) { [IO.Compression.ZipFileExtensions]::ExtractToFile($e, $o, $true) }; $a.Dispose(); if (-not $e) { exit 1 }"
if errorlevel 2 goto :nozip
if errorlevel 1 goto :oldzip

:run
set "ZARG="
if not "%A1%"=="" set ZARG=-Zip "%A1%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -BatDir "%HERE%" %ZARG%
goto :end

:nozip
echo.
echo  [FIX] No code zip (OLYMPUS_BACKUP_...zip) was found in Downloads or on the Desktop. Download the zip and its .sha256.txt into Downloads, then double-click SETUP_EVERYTHING.bat again. If it still fails, send a photo of this window.
goto :end

:oldzip
echo.
echo  [FIX] The newest code zip in Downloads is too old or damaged (no setup script in it). Download the newest zip and its .sha256.txt into Downloads, then double-click SETUP_EVERYTHING.bat again. If it still fails, send a photo of this window.
goto :end

:nops
echo.
echo  [FIX] Windows PowerShell was not found on this PC. Send a photo of this window to Claude.

:end
echo.
pause
endlocal
