<#
BOT LITE (2026-11-03): the bot on very little memory. One click (tools\bat\BOT_LITE.bat):
  1. turns LITE mode on (data\lite.json {"on": true}; engine\lite.py): the bot's read-only add-ons (Bot Brain, Trade
     pictures, the paper second strategies' worker process, AI watch, Mind, the dashboard backtest) are off and it keeps
     100 days of history instead of 5 years. Trades exactly the same (tests\test_lite.py). About 690 MB -> 180 MB.
  2. starts NinjaTrader if it is not running (with the workspace you last saved: make that the empty "LITE" one, below)
  3. starts the bot server in LITE mode, or restarts it when it is already running and FLAT (refused during a trade:
     nothing is restarted then; run BOT_LITE again after the trade). Never arms anything: the bot resumes exactly as it
     was (a Sim bot by itself, a real account only with auto-resume on, as with the dashboard's Restart button).
  4. NinjaTrader + the bot get AboveNormal priority, background apps BelowNormal, idle apps trimmed when memory is short
     (scripts\pc_keeper.ps1 -Bot once; it never closes anything)
  5. prints the NinjaTrader memory checklist

  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\bot_lite.ps1 [-Off] [-NoNinja] [-DryRun]
  -Off: LITE off again (full bot with every add-on), restarts the server the same way.
#>
param(
    [switch]$Off,
    [switch]$NoNinja,
    [switch]$DryRun,
    [int]$Port = 0
)
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
if ($Port -le 0) { if ($env:PORT) { $Port = [int]$env:PORT } else { $Port = 8766 } }
$Base = "http://127.0.0.1:$Port"
function Say-Ok([string]$t) { Write-Host " [OK]  $t" -ForegroundColor Green }
function Say-Fix([string]$t) { Write-Host " [FIX] $t" -ForegroundColor Yellow }
function Say([string]$t) { Write-Host "       $t" }

function Test-Server {
    try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri "$Base/api/health/ping"; return $true } catch { return $false }
}

function Find-NinjaTrader {
    $p = Get-Process -Name NinjaTrader -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($p -and $p.Path) { return $p.Path }
    $cands = @()
    foreach ($b in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramW6432, 'C:\Program Files')) {
        if ($b) { $cands += (Join-Path $b 'NinjaTrader 8\bin\NinjaTrader.exe') }
    }
    foreach ($c in $cands) { if ($c -and (Test-Path -LiteralPath $c)) { return $c } }
    return $null
}

Write-Host ""
Write-Host " BOT LITE - the bot on very little memory" -ForegroundColor Cyan
Write-Host ""

# ---- 1. the switch (data\lite.json, gitignored; read once when the server starts)
$on = -not $Off
$lite = Join-Path $Root 'data\lite.json'
$json = '{"on": ' + $(if ($on) { 'true' } else { 'false' }) + ', "hist_days": 100}'
if ($DryRun) { Say "DRY RUN: would write $lite = $json" }
else {
    try {
        [System.IO.File]::WriteAllText($lite, $json, (New-Object System.Text.UTF8Encoding($false)))
        if ($on) { Say-Ok "LITE mode on (add-ons off, 100 days of history; trades the same)" } else { Say-Ok "LITE mode off (the full bot)" }
    } catch { Say-Fix "could not write data\lite.json: $($_.Exception.Message)"; exit 1 }
}

# ---- 2. NinjaTrader (the last saved workspace opens: save the empty LITE one, checklist below)
if (-not $NoNinja) {
    $nt = Get-Process -Name NinjaTrader -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($nt) { Say-Ok "NinjaTrader is running ($([int]($nt.WorkingSet64 / 1MB)) MB)" }
    else {
        $exe = Find-NinjaTrader
        if (-not $exe) { Say-Fix "NinjaTrader.exe not found: start NinjaTrader yourself" }
        elseif ($DryRun) { Say "DRY RUN: would start $exe" }
        else {
            Start-Process -FilePath $exe | Out-Null
            Say-Ok "NinjaTrader started: log in, it connects by itself if 'Connect on startup' is ticked"
        }
    }
}

# ---- 3. the bot server in LITE mode
if (Test-Server) {
    if ($DryRun) { Say "DRY RUN: would ask the server to restart (only when flat)" }
    else {
        try {
            $r = Invoke-RestMethod -Method Post -TimeoutSec 10 -Uri "$Base/api/next/botctl/restart" -ContentType 'application/json' -Body '{}'
            Say-Ok "bot server restarting in $(if ($on) { 'LITE' } else { 'full' }) mode (back in ~10 s, the bot resumes as it was)"
        } catch {
            $why = ''
            try { $why = (($_.ErrorDetails.Message | ConvertFrom-Json).error) } catch { }
            if (-not $why) { $why = $_.Exception.Message }
            Say-Fix "not restarted now: $why"
            Say "The switch is saved: it takes effect at the next restart. Double-click BOT_LITE again after the trade."
        }
    }
} else {
    if ($DryRun) { Say "DRY RUN: would start scripts\run_bot.ps1 hidden" }
    else {
        Start-Process powershell -WindowStyle Hidden -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
            '-File', (Join-Path $Root 'scripts\run_bot.ps1')) | Out-Null
        $up = $false
        for ($i = 0; $i -lt 90; $i++) { Start-Sleep -Seconds 2; if (Test-Server) { $up = $true; break } }
        if ($up) { Say-Ok "bot server started in $(if ($on) { 'LITE' } else { 'full' }) mode (it resumes the bot as you left it)" }
        else { Say-Fix "the server did not answer in 3 minutes: double-click HEALTH_CHECK.bat (log: logs\server-YYYYMMDD.log)" }
    }
}

# ---- 4. priorities (once; the LiquidityEngine-Keeper task repeats it every 15 min when CLEAN_PC set it up)
$keeper = Join-Path $PSScriptRoot 'pc_keeper.ps1'
if (Test-Path -LiteralPath $keeper) {
    if ($DryRun) { & $keeper -Bot -DryRun | Out-Null } else { & $keeper -Bot | Out-Null }
    Say-Ok "NinjaTrader + bot first, background apps lowered"
}
try {
    $os = Get-CimInstance Win32_OperatingSystem
    $used = [int](100 - 100 * $os.FreePhysicalMemory / $os.TotalVisibleMemorySize)
    Say "Memory in use now: $used%  (aim: under 80%)"
} catch { }

# ---- 5. the NinjaTrader memory checklist (once; plain words)
Write-Host ""
Write-Host " NinjaTrader memory checklist (do once, after 4:05 PM ET):" -ForegroundColor Cyan
Say "1. Close every chart, Market Analyzer, SuperDOM and Strategies tab. Keep only the Control Center."
Say "   (The LE_Feed add-on gives the bot its bars with no chart: tools\bat\NO_CHART_MODE.bat, then F5 once.)"
Say "2. Workspaces > New > name it LITE > Workspaces > Save. NinjaTrader opens it next time."
Say "3. Control Center: close the Orders, Executions, Strategies and Log tabs you don't read (Accounts can stay)."
Say "4. Tools > Options > Market data: untick 'Show Tick Replay'. Tools > Database Management: Repair DB once a month."
Say "5. If you keep one chart: 30 days of 5 minute bars, no Tick Replay, no extra indicators."
Say "6. Close Edge / Chrome while trading (each tab is 100-300 MB). Pause OneDrive syncing."
Write-Host ""
