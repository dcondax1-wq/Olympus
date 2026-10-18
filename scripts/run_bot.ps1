<#
Liquidity Engine supervisor (Windows PowerShell 5.1).

Starts `python server.py` from the project root and restarts it whenever it exits, with back-off
5 s, 15 s, 60 s (cap; reset after a run that lasted 10 min). Output (stdout + stderr) goes to
logs\server-YYYYMMDD.log (a new file each day, files older than 30 days are deleted).

  .\scripts\run_bot.ps1                 # port 8766 (or $env:PORT / .env.local.ps1)
  .\scripts\run_bot.ps1 -Port 8770
  .\scripts\run_bot.ps1 -DryRun         # show what would run, start nothing

Refuses to start when something already listens on the port or another supervisor is running.
Stop it with scripts\stop_bot.ps1 (creates logs\supervisor.stop, then ends the server).
#>
param(
    [int]$Port = 0,
    [string]$Python = "",
    [switch]$DryRun
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
$LogDir = Join-Path $Root 'logs'
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$PidFile = Join-Path $LogDir 'supervisor.pid'
$StopFile = Join-Path $LogDir 'supervisor.stop'
$Utf8 = New-Object System.Text.UTF8Encoding($false)

function Get-LogPath { Join-Path $LogDir ("server-{0}.log" -f (Get-Date -Format 'yyyyMMdd')) }

function Write-Log([string]$Line) {
    try { [System.IO.File]::AppendAllText((Get-LogPath), $Line + "`r`n", $Utf8) } catch { }
}

function Write-Sup([string]$Text) {
    $line = "[supervisor] {0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Text
    Write-Log $line
    Write-Host $line
}

function Test-PortListening([int]$P) {
    try {
        $c = Get-NetTCPConnection -State Listen -LocalPort $P -ErrorAction Stop
        return [bool]$c
    } catch { return $false }
}

# ---- environment: credentials file is dot-sourced, its values are never printed
$envFile = Join-Path $Root '.env.local.ps1'
if (Test-Path -LiteralPath $envFile) {
    try { . $envFile; $envNote = 'loaded .env.local.ps1 (values not shown)' }
    catch { $envNote = "could not load .env.local.ps1: $($_.Exception.Message)" }
} else { $envNote = 'no .env.local.ps1 (paper only)' }

if ($Port -le 0) { if ($env:PORT) { $Port = [int]$env:PORT } else { $Port = 8766 } }
$env:PORT = "$Port"
$env:PYTHONUNBUFFERED = '1'
if (-not $env:LE_HEARTBEAT) { $env:LE_HEARTBEAT = '1' }   # the always-on PC tells the cloud monitor it is alive (engine/heartbeat.py)
$env:PYTHONIOENCODING = 'utf-8'
try { [Console]::OutputEncoding = $Utf8 } catch { }

if (-not $Python) { if ($env:LE_PYTHON) { $Python = $env:LE_PYTHON } }
if (-not $Python) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $Python = $cmd.Source }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) {
    Write-Sup "python not found (pass -Python <path> or set LE_PYTHON); exiting"
    exit 2
}

if ($DryRun) {
    Write-Host "DRY RUN - nothing started"
    Write-Host "  root      : $Root"
    Write-Host "  python    : $Python"
    Write-Host "  command   : `"$Python`" -u server.py   (PORT=$Port, HOST=$(if ($env:HOST) { $env:HOST } else { '0.0.0.0' }))"
    Write-Host "  env       : $envNote"
    Write-Host "  log       : $(Get-LogPath)"
    Write-Host "  port busy : $(Test-PortListening $Port)"
    exit 0
}

# ---- single instance: one supervisor per user session, and nothing else on the port
$mutex = New-Object System.Threading.Mutex($false, 'Local\LiquidityEngineSupervisor')
$haveMutex = $false
try { $haveMutex = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $haveMutex = $true }
if (-not $haveMutex) {
    Write-Sup "another supervisor is already running (mutex held); exiting"
    exit 0
}
if (Test-PortListening $Port) {
    Write-Sup "port $Port is already in use by another process; not starting a second copy"
    $mutex.ReleaseMutex()
    exit 0
}

Remove-Item -LiteralPath $StopFile -ErrorAction SilentlyContinue
Set-Content -LiteralPath $PidFile -Value $PID -Encoding ASCII
Get-ChildItem -LiteralPath $LogDir -Filter 'server-*.log' -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -ErrorAction SilentlyContinue

Write-Sup "supervisor pid $PID starting; port $Port; python $Python; $envNote"
$delays = @(5, 15, 60)
$fail = 0
try {
    while ($true) {
        if (Test-Path -LiteralPath $StopFile) { Write-Sup "stop file found; exiting"; break }
        if (Test-PortListening $Port) {
            Write-Sup "port $Port taken by another process; waiting 60 s"
            Start-Sleep -Seconds 60
            continue
        }
        $t0 = Get-Date
        Write-Sup "starting server.py (attempt after $fail consecutive short runs)"
        & $Python -u server.py 2>&1 | ForEach-Object {
            Write-Log ("{0} {1}" -f (Get-Date -Format 'HH:mm:ss'), "$_")
        }
        $code = $LASTEXITCODE
        $ran = [int]((Get-Date) - $t0).TotalSeconds
        if (Test-Path -LiteralPath $StopFile) { Write-Sup "server exited (code $code) after stop request; exiting"; break }
        if ($ran -ge 600) { $fail = 0 }
        $wait = $delays[[Math]::Min($fail, $delays.Count - 1)]
        $fail++
        Write-Sup "server exited with code $code after $ran s; restarting in $wait s"
        Start-Sleep -Seconds $wait
    }
} finally {
    Remove-Item -LiteralPath $PidFile -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $StopFile -ErrorAction SilentlyContinue
    try { $mutex.ReleaseMutex() } catch { }
    Write-Sup "supervisor stopped"
}
