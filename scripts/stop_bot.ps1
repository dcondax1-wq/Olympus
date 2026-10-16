<#
Graceful stop of the Liquidity Engine.

  .\scripts\stop_bot.ps1                   # POST /api/live/stop (clears auto-resume), stop server + supervisor
  .\scripts\stop_bot.ps1 -KeepAutostart    # stop server + supervisor but leave the bot set to auto-resume next start
  .\scripts\stop_bot.ps1 -RestartServer    # only restart server.py (supervisor brings it back, bot auto-resumes)
  .\scripts\stop_bot.ps1 -DryRun           # print what would happen
#>
param(
    [int]$Port = 0,
    [switch]$KeepAutostart,
    [switch]$RestartServer,
    [switch]$DryRun
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root 'logs'
$PidFile = Join-Path $LogDir 'supervisor.pid'
$StopFile = Join-Path $LogDir 'supervisor.stop'
if ($Port -le 0) { if ($env:PORT) { $Port = [int]$env:PORT } else { $Port = 8766 } }
$Base = "http://127.0.0.1:$Port"

$serverPids = @()
try { $serverPids = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop | Select-Object -ExpandProperty OwningProcess -Unique) } catch { }
$supPid = $null
if (Test-Path -LiteralPath $PidFile) { $supPid = [int](Get-Content -LiteralPath $PidFile -TotalCount 1) }

if ($DryRun) {
    Write-Host "DRY RUN - nothing stopped"
    Write-Host "  server pids on port $Port : $($serverPids -join ', ')"
    Write-Host "  supervisor pid          : $supPid"
    if (-not $KeepAutostart -and -not $RestartServer) { Write-Host "  would POST $Base/api/live/stop (clears data\autostart.json)" }
    if (-not $RestartServer) { Write-Host "  would create $StopFile and stop the supervisor" }
    Write-Host "  would stop the server process(es)"
    exit 0
}

if (-not $KeepAutostart -and -not $RestartServer) {
    try {
        $r = Invoke-RestMethod -Method Post -Uri "$Base/api/live/stop" -TimeoutSec 10 -ContentType 'application/json' -Body '{}'
        Write-Host "bot stopped via API (ok=$($r.ok)); auto-resume cleared"
    } catch { Write-Host "API stop failed ($($_.Exception.Message)); continuing" }
}

if (-not $RestartServer) {
    if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
    Set-Content -LiteralPath $StopFile -Value (Get-Date -Format o) -Encoding ASCII
}

foreach ($p in $serverPids) {
    if ($p -and $p -ne 0) {
        try { Stop-Process -Id $p -Force -ErrorAction Stop; Write-Host "server process $p stopped" }
        catch { Write-Host "could not stop server process ${p}: $($_.Exception.Message)" }
    }
}
if (-not $serverPids) { Write-Host "no server listening on port $Port" }

if ($RestartServer) { Write-Host "supervisor will restart server.py in ~5 s"; exit 0 }

if ($supPid) {
    $deadline = (Get-Date).AddSeconds(10)
    while ((Get-Process -Id $supPid -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
    $sp = Get-Process -Id $supPid -ErrorAction SilentlyContinue
    if ($sp) {
        Stop-Process -Id $supPid -Force -ErrorAction SilentlyContinue
        Write-Host "supervisor $supPid did not exit in 10 s; stopped it"
        Remove-Item -LiteralPath $PidFile -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $StopFile -ErrorAction SilentlyContinue
    } else { Write-Host "supervisor $supPid exited" }
} else {
    Write-Host "no supervisor pid file (was it started by run_bot.ps1?)"
    Remove-Item -LiteralPath $StopFile -ErrorAction SilentlyContinue
}
