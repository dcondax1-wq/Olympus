<#
Creates the Windows Task Scheduler task "LiquidityEngineOps": every 5 minutes (and at logon) it runs
scripts\ops_tick.py with pythonw (no window) = python -m engine.ops_checks --tick. Read-only helper: it never starts,
stops, arms or routes anything. What it does when due (ET): 01:40 pre-session check push, 16:05 day summary push,
Sunday evening week report push, internet / NinjaTrader drop + recovery pushes, MFFU 5-day inactivity reminder, eval
passed / failed push, contract roll reminder, nightly backup (backups\, 14 days) + log rotation (logs\).
Log: logs\ops-YYYYMMDD.log. Turn the phone pushes off without removing the task: set LE_OPS_PUSH=0 for the user.

  powershell -ExecutionPolicy Bypass -File .\scripts\install_ops_task.ps1          (SETUP_SHORTCUTS.bat runs this)
  powershell -ExecutionPolicy Bypass -File .\scripts\install_ops_task.ps1 -DryRun
  powershell -ExecutionPolicy Bypass -File .\scripts\install_ops_task.ps1 -Remove
#>
param(
    [string]$Python = "",
    [string]$User = "",          # DOMAIN\name the task runs as (ONE_TIME_SETUP passes the signed-in owner from its elevated part); default: you
    [switch]$DryRun,
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$TaskName = 'LiquidityEngineOps'
$Root = Split-Path -Parent $PSScriptRoot
$Tick = Join-Path $PSScriptRoot 'ops_tick.py'
if (-not $User) { $User = "$env:USERDOMAIN\$env:USERNAME" }

if ($Remove) {
    if ($DryRun) { Write-Host "would remove the task $TaskName"; exit 0 }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK]  task $TaskName removed"
    exit 0
}

if (-not $Python) {
    if ($env:LE_PYTHON) { $Python = $env:LE_PYTHON }
    else {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) { $Python = $cmd.Source }
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) {
    Write-Host "[FIX] python not found: install Python 3.12 (tick 'Add python.exe to PATH') or pass -Python C:\path\to\python.exe"
    exit 1
}
if ($Python -like '*\WindowsApps\*') { Write-Host "[WARN] python is the Microsoft Store alias ($Python); pass -Python with the real python.exe if the task does nothing" }
$Pyw = Join-Path (Split-Path -Parent $Python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $Pyw)) { $Pyw = $Python }

$argLine = "-X utf8 `"$Tick`""
$action = New-ScheduledTaskAction -Execute $Pyw -Argument $argLine -WorkingDirectory $Root
$daily = New-ScheduledTaskTrigger -Daily -At '00:00'
$every5 = New-ScheduledTaskTrigger -Once -At '00:00' -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 1)
$daily.Repetition = $every5.Repetition                  # every 5 min, all day, every day
$logon = New-ScheduledTaskTrigger -AtLogOn -User $User
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
$desc = "Liquidity Engine helper: health checks, phone notices, nightly backup (read-only). Installed $(Get-Date -Format 'yyyy-MM-dd HH:mm') from $Root"
$task = New-ScheduledTask -Action $action -Trigger @($daily, $logon) -Settings $settings -Principal $principal -Description $desc

if ($DryRun) {
    Write-Host "DRY RUN - nothing registered. Would create:"
    Write-Host "  task      : $TaskName (runs as $User, only when logged on, not elevated)"
    Write-Host "  program   : $Pyw $argLine"
    Write-Host "  start in  : $Root"
    Write-Host "  triggers  : every 5 min all day; at logon"
    exit 0
}

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
try {
    Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
} catch {
    Write-Host "[FIX] could not create the task: $($_.Exception.Message)"
    Write-Host "      If it says 'Access is denied', run SETUP_SHORTCUTS once with right-click > Run as administrator."
    exit 1
}
Write-Host "[OK]  helper task $TaskName runs every 5 minutes (phone notices, nightly backup)"
