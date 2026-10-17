<#
Helper run by the tasks that scripts\schedule_pc.ps1 creates. Not meant to be run by hand.
  -Mode wake   start the LiquidityEngine supervisor task (if it is not running) and NinjaTrader (if a path is given)
  -Mode sleep  hibernate, unless the bot reports an open position: then retry every 10 min until 18:00 ET
Lines go to logs\schedule-YYYYMMDD.log.
#>
param(
    [ValidateSet('wake', 'sleep')][string]$Mode,
    [int]$Port = 8766,
    [string]$NinjaTrader = ""
)
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root 'logs'
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
function Log([string]$t) {
    $line = "[schedule] {0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $t
    try { Add-Content -LiteralPath (Join-Path $LogDir ("schedule-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))) -Value $line } catch { }
    Write-Host $line
}
function Get-BotState {
    try { return Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/live/state" -TimeoutSec 5 } catch { return $null }
}

if ($Mode -eq 'wake') {
    Log "wake: starting"
    $bot = Get-ScheduledTask -TaskName 'LiquidityEngine' -ErrorAction SilentlyContinue
    if ($bot) {
        if ($bot.State -ne 'Running') { Start-ScheduledTask -TaskName 'LiquidityEngine'; Log "started task LiquidityEngine" }
        else { Log "task LiquidityEngine already running" }
    } else { Log "task LiquidityEngine is missing: run scripts\install_autostart.ps1" }
    if ($NinjaTrader) {
        if (Get-Process -Name 'NinjaTrader' -ErrorAction SilentlyContinue) { Log "NinjaTrader already running" }
        else { Start-Process -FilePath $NinjaTrader; Log "started NinjaTrader ($NinjaTrader)" }
    }
    # keep the screen from sleeping for a minute so the session is fully back, then let the bot's keep-awake take over
    Start-Sleep -Seconds 60
    $s = Get-BotState
    if ($s) { Log ("bot state: running={0} model={1}" -f $s.running, $s.state.model_state) } else { Log "bot not answering yet on port $Port (the supervisor may still be starting)" }
    exit 0
}

# sleep: never hibernate on top of an open position
$et = [TimeZoneInfo]::FindSystemTimeZoneById('Eastern Standard Time')
$deadline = [TimeZoneInfo]::ConvertTimeToUtc([DateTime]::SpecifyKind((Get-Date).Date.AddHours(18), 'Unspecified'), $et)
while ($true) {
    $s = Get-BotState
    $open = $false
    if ($s -and $s.state -and $s.state.position) { $open = $true }
    if (-not $open) { break }
    if ((Get-Date).ToUniversalTime() -ge $deadline) { Log "sleep: position still open at 18:00 ET, giving up (PC stays on)"; exit 0 }
    Log "sleep: position open, retrying in 10 min"
    Start-Sleep -Seconds 600
}
if ($NinjaTrader -and (Get-Process -Name 'NinjaTrader' -ErrorAction SilentlyContinue)) { Log "NinjaTrader left running (hibernation keeps it)" }
Log "sleep: hibernating"
Start-Sleep -Seconds 5
& shutdown.exe /h
