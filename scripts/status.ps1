<#
Liquidity Engine status: server up/down, bot running, adapter, data age, last error, watchdog, task, log tail.
  .\scripts\status.ps1            # port 8766
  .\scripts\status.ps1 -Port 8765
#>
param([int]$Port = 0, [int]$Tail = 8)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
if ($Port -le 0) { if ($env:PORT) { $Port = [int]$env:PORT } else { $Port = 8766 } }
$Base = "http://127.0.0.1:$Port"

$up = $false
try {
    $ping = Invoke-RestMethod -Uri "$Base/api/health/ping" -TimeoutSec 5
    $up = [bool]$ping.ok
} catch { }

if (-not $up) {
    Write-Host "SERVER : DOWN (nothing answering $Base/api/health/ping)"
} else {
    Write-Host ("SERVER : UP   uptime {0} s" -f $ping.uptime_s)
    try {
        $s = Invoke-RestMethod -Uri "$Base/api/live/state" -TimeoutSec 10
        $h = $s.health
        $lastPoll = if ($s.last_poll) { ([DateTimeOffset]::FromUnixTimeSeconds([long]$s.last_poll)).LocalDateTime } else { 'never' }
        Write-Host ("BOT    : {0}   adapter={1}   kill={2}   trades today={3}   day P&L routed={4}" -f `
            $(if ($s.running) { 'RUNNING' } else { 'stopped' }), $s.cfg.adapter, $s.kill, $s.trades_today, $s.day_pnl_routed)
        Write-Host ("DATA   : data_age_s={0}   stale={1}   market_open={2}   last poll {3}   health.ok={4}" -f `
            $h.data_age_s, $h.stale, $h.market_open, $lastPoll, $h.ok)
        Write-Host ("ERROR  : {0}" -f $(if ($h.last_error) { $h.last_error } else { 'none' }))
    } catch { Write-Host "BOT    : /api/live/state failed: $($_.Exception.Message)" }
    try {
        $w = Invoke-RestMethod -Uri "$Base/api/health/watchdog" -TimeoutSec 5
        $iss = if ($w.issues -and @($w.issues).Count) { (@($w.issues) | ForEach-Object { $_.key }) -join ', ' } else { 'none' }
        Write-Host ("WATCH  : ok={0}   issues={1}   keep-awake held={2}   autostart record={3}" -f $w.ok, $iss, $w.keepawake.held, $w.autostart_record)
        if ($w.autostart -and $w.autostart.reason) { Write-Host ("RESUME : resumed={0}   {1}" -f $w.autostart.resumed, $w.autostart.reason) }
    } catch { Write-Host "WATCH  : /api/health/watchdog not available" }
}

$pidFile = Join-Path $Root 'logs\supervisor.pid'
if (Test-Path -LiteralPath $pidFile) {
    $sp = [int](Get-Content -LiteralPath $pidFile -TotalCount 1)
    Write-Host ("SUPER  : pid {0} {1}" -f $sp, $(if (Get-Process -Id $sp -ErrorAction SilentlyContinue) { 'alive' } else { 'NOT running (stale pid file)' }))
} else { Write-Host "SUPER  : no supervisor pid file" }

try {
    $t = Get-ScheduledTask -TaskName 'LiquidityEngine' -ErrorAction Stop
    $i = $t | Get-ScheduledTaskInfo
    Write-Host ("TASK   : LiquidityEngine state={0} last run={1} result={2}" -f $t.State, $i.LastRunTime, $i.LastTaskResult)
} catch { Write-Host "TASK   : LiquidityEngine not installed" }

$log = Join-Path $Root ("logs\server-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
if (Test-Path -LiteralPath $log) {
    Write-Host "LOG    : $log (last $Tail lines)"
    Get-Content -LiteralPath $log -Tail $Tail -Encoding UTF8 | ForEach-Object { Write-Host "  $_" }
} else { Write-Host "LOG    : no log for today yet" }
