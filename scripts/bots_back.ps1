<#
BOTS BACK (double-click BOTS_BACK.bat). Owner 2026-11-12: "We need to get these bots running again." The GitHub account is gone;
the bots never needed it to trade, only their reporting did. One double-click, safe to repeat (docs\BOTS_BACK.md):

  1 GITHUB   GitHub-free mode on: the file %USERPROFILE%\.olympus\no_github (engine\nogithub.py: the heartbeat goes to logs\pc_hb,
             the phone live push, remote control and git auto-update stay off) and credential.interactive=never in this folder's
             git config (no GitHub sign-in window). Applies when the bot server starts.
  2 NINJA    NinjaTrader 8 running (opened when it is closed) and LE_BarFeed's MNQ bars fresh (waits up to 5 minutes while the
             market is open; tools\bots_back.py --wait-feed)
  3 BOT      the bot server started hidden (scripts\run_bot.ps1, the same start as UPDATE.bat) when it does not answer, then your
             last start resumed ONLY if it was paper or a NinjaTrader Sim account (tools\bots_back.py --resume-paper). A real account
             is never armed here: that stays START_BOT.bat, where you type the live phrase yourself. A running bot is left alone.
  4 REPORT   the 15-minute task OlympusPCReport (scripts\pc_report_task.ps1 -> tools\pc_report.py): phone alerts on your private
             ntfy topic + the site's status. One test push the first time.
  5 CARD     six lines: bots, feed, last trade, drawdown left, reporting, next window (tools\pc_report.py)

  -DryRun    say what it would do, change nothing         -Remove   undo 1 and 4 (UNDO_BOTS_BACK.bat)
It never stops or restarts a running bot, never places an order, never touches live_model*.json, engine\ or NinjaTrader settings.
Tests: tests\test_bots_back.py (pwsh with a fake python; LE_BB_T_NT=1|0 and LE_BB_T_LOG=<file> stand in for Windows-only steps).
#>
param(
    [switch]$DryRun,
    [switch]$Remove,
    [string]$Python = "",
    [int]$FeedWait = 300
)

$ErrorActionPreference = 'Continue'
trap {
    Write-Host ''
    Write-Host '  [FIX] Something unexpected stopped this: take a photo of this window and send it to Claude.' -ForegroundColor Red
    exit 1
}
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
function J2([string]$A, [string]$B) { return [System.IO.Path]::Combine($A, $B) }
function Line([string]$Kind, [string]$Text) {
    $c = 'Gray'; if ($Kind -eq 'OK') { $c = 'Green' } elseif ($Kind -eq 'FIX') { $c = 'Red' } elseif ($Kind -eq 'SKIP') { $c = 'Yellow' }
    Write-Host ("  [{0}] {1}" -f $Kind, $Text) -ForegroundColor $c
}
function TLog([string]$What) {
    # tests: a Windows-only step is written to LE_BB_T_LOG instead of being done
    if ($env:LE_BB_T_LOG) { Add-Content -LiteralPath $env:LE_BB_T_LOG -Value $What; return $true }
    return $false
}
function P($Obj, [string]$Name) {
    if ($null -eq $Obj) { return $null }
    $p = $Obj.PSObject.Properties[$Name]; if ($p) { return $p.Value }; return $null
}

$Home1 = $env:OLYMPUS_HOME
if (-not $Home1) {
    $up = $env:USERPROFILE; if (-not $up) { $up = $HOME }
    $Home1 = J2 $up '.olympus'
}
$Marker = J2 $Home1 'no_github'
$StateFile = J2 (J2 $Root 'data') 'bots_back.json'
$TaskScript = J2 $PSScriptRoot 'pc_report_task.ps1'
$RunBot = J2 $PSScriptRoot 'run_bot.ps1'
$Helper = J2 (J2 $Root 'tools') 'bots_back.py'
$Report = J2 (J2 $Root 'tools') 'pc_report.py'

function Read-State {
    try { if (Test-Path -LiteralPath $StateFile) { return (Get-Content -LiteralPath $StateFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop) } } catch { }
    return $null
}
function Save-State([hashtable]$H) {
    try {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $StateFile) | Out-Null
        Set-Content -LiteralPath $StateFile -Value ($H | ConvertTo-Json -Depth 4) -Encoding ASCII
    } catch { }
}
function Git-Exe {
    $g = Get-Command git -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($g) { return $g.Source }
    return $null
}

Write-Host ''
Write-Host '  ==== BOTS BACK: the bots and their reporting, without GitHub ====' -ForegroundColor Cyan
Write-Host ''

# ------------------------------------------------------------------ python + the new code
if (-not $Python) {
    if ($env:LE_PYTHON) { $Python = $env:LE_PYTHON }
    else {
        $cmd = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd) { $Python = $cmd.Source }
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) {
    Line 'FIX' 'Python not found: double-click ONE_TIME_SETUP.bat first, then BOTS_BACK.bat again.'
    exit 1
}
if (-not (Test-Path -LiteralPath $Helper) -or -not (Test-Path -LiteralPath $Report) -or -not (Test-Path -LiteralPath $TaskScript)) {
    Line 'FIX' 'This bot folder has old code: put the new code zip in Downloads and double-click UPDATE_FROM_ZIP.bat first (docs\BOTS_BACK.md step 1).'
    exit 1
}
$env:PYTHONIOENCODING = 'utf-8'
$st = Read-State
$state = @{ marker_made = [bool](P $st 'marker_made'); git_set = [bool](P $st 'git_set'); git_prev = [string](P $st 'git_prev'); t = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }

# ------------------------------------------------------------------ undo (UNDO_BOTS_BACK.bat)
if ($Remove) {
    if ($DryRun) { Write-Host "  DRY RUN - would remove the task OlympusPCReport, the file $Marker (if BOTS_BACK made it) and the git setting it made"; exit 0 }
    & $TaskScript -Remove
    if ($state.marker_made -and (Test-Path -LiteralPath $Marker)) {
        Remove-Item -LiteralPath $Marker -Force -ErrorAction SilentlyContinue
        Line 'OK' 'GitHub-free mode file removed (the bot goes back to its GitHub behaviour at its next start)'
    } else { Line 'OK' 'GitHub-free mode file left as it was (BOTS_BACK did not make it)' }
    $git = Git-Exe
    if ($state.git_set -and $git -and (Test-Path -LiteralPath (J2 $Root '.git'))) {
        if ($state.git_prev) { & $git -C $Root config --local credential.interactive $state.git_prev 2>$null | Out-Null }
        else { & $git -C $Root config --local --unset credential.interactive 2>$null | Out-Null }
        Line 'OK' 'git sign-in setting put back'
    }
    $state.marker_made = $false; $state.git_set = $false; $state.git_prev = ''
    Save-State $state
    Write-Host ''
    Write-Host '  Undone. The bot itself was not touched. Your ntfy topic stays in your settings folder.'
    exit 0
}

if ($DryRun) {
    Write-Host '  DRY RUN - nothing changed. Would:'
    Write-Host "    1 GitHub   : create $Marker if missing; git config --local credential.interactive never"
    Write-Host "    2 Ninja    : open NinjaTrader 8 if closed; wait up to $([int]($FeedWait / 60)) min for fresh LE_BarFeed bars ($Python tools\bots_back.py --wait-feed)"
    Write-Host "    3 Bot      : start scripts\run_bot.ps1 hidden if the server does not answer; resume a paper / Sim start only"
    Write-Host '    4 Report   : install the 15-minute task OlympusPCReport (tools\pc_report.py); one test push the first time'
    Write-Host '    5 Card     : six lines (tools\pc_report.py)'
    exit 0
}

# ------------------------------------------------------------------ 1 GitHub off
$madeNow = $false
try {
    New-Item -ItemType Directory -Force -Path $Home1 | Out-Null
    if (-not (Test-Path -LiteralPath $Marker)) {
        Set-Content -LiteralPath $Marker -Value 'GitHub-free bot mode (BOTS_BACK.bat). Delete this file or run UNDO_BOTS_BACK.bat to undo.' -Encoding ASCII
        $state.marker_made = $true; $madeNow = $true
        Line 'OK' '1/5 GitHub pushes off (GitHub-free mode on; it applies when the bot server starts)'
    } else { Line 'OK' '1/5 GitHub pushes off (GitHub-free mode already on)' }
} catch { Line 'SKIP' "1/5 could not write ${Marker}: $($_.Exception.Message)" }
try {
    $git = Git-Exe
    if ($git -and (Test-Path -LiteralPath (J2 $Root '.git'))) {
        $cur = (& $git -C $Root config --local --get credential.interactive 2>$null | Select-Object -First 1)
        if ("$cur" -ne 'never') {
            if (-not $state.git_set) { $state.git_prev = "$cur" }
            & $git -C $Root config --local credential.interactive never 2>$null | Out-Null
            $state.git_set = $true
        }
    }
} catch { }
Save-State $state

# ------------------------------------------------------------------ 2 NinjaTrader + its bars
$ntRunning = $false
if ($env:LE_BB_T_NT) { $ntRunning = ($env:LE_BB_T_NT -eq '1') }
else { $ntRunning = (@(Get-Process -Name 'NinjaTrader' -ErrorAction SilentlyContinue).Count -gt 0) }
if ($ntRunning) { Line 'OK' '2/5 NinjaTrader is running' }
else {
    $ntExe = $env:NINJATRADER_EXE
    if (-not $ntExe) { $ntExe = 'C:\Program Files\NinjaTrader 8\bin\NinjaTrader.exe' }
    if (TLog "START NT $ntExe") { Line 'OK' '2/5 opening NinjaTrader: log in and connect, this window waits' }
    elseif (Test-Path -LiteralPath $ntExe) {
        try { Start-Process -FilePath $ntExe -WorkingDirectory (Split-Path -Parent $ntExe) | Out-Null; Line 'OK' '2/5 opening NinjaTrader: log in and connect, this window waits' }
        catch { Line 'FIX' "2/5 could not open NinjaTrader: open it yourself ($($_.Exception.Message))" }
    } else { Line 'FIX' '2/5 NinjaTrader 8 is not running and was not found: open it yourself and log in' }
}
& $Python -X utf8 $Helper --wait-feed $FeedWait

# ------------------------------------------------------------------ 3 the bot (never armed here)
& $Python -X utf8 $Helper --server-up
$wasUp = ($LASTEXITCODE -eq 0)
if ($wasUp) {
    Line 'OK' '3/5 the bot server is already running (left alone)'
    if ($madeNow) {
        Line 'SKIP' '    it started before GitHub-free mode: when it is flat and the market is closed, STOP_BOT.bat then BOTS_BACK.bat once'
    }
} else {
    if (-not (TLog "START SERVER $RunBot")) {
        try {
            Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', "`"$RunBot`"") | Out-Null
        } catch { Line 'FIX' "3/5 could not start the bot server: $($_.Exception.Message)" }
    }
    Line 'OK' '3/5 starting the bot server (hidden window, log in logs\server-YYYYMMDD.log)'
    & $Python -X utf8 $Helper --wait-server 120
}
& $Python -X utf8 $Helper --resume-paper

# ------------------------------------------------------------------ 4 reporting (no GitHub, free)
& $TaskScript -Python $Python
& $Python -X utf8 $Report --test

# ------------------------------------------------------------------ 5 the card
Write-Host ''
Write-Host '  ---- status ----' -ForegroundColor Cyan
& $Python -X utf8 $Report
Write-Host ''
Write-Host '  Safe to double-click again any time. Undo: UNDO_BOTS_BACK.bat. More: docs\BOTS_BACK.md'
exit 0
