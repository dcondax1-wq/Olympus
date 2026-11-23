<#
WEEKLY BACKUP task (tools\bat\BACKUP_SETUP.bat installs it; docs\DISASTER_RECOVERY.md "Second backup").

  default   installs (or replaces) the Windows task "OlympusWeeklyBackup": every Sunday at 11:37, and later the same day when the
            PC was off then, it runs tools\second_backup.py --weekly --quiet with pythonw (no window), only while you are signed
            in: the code zip into your synced folder and the push to your mirror repository, then one phone push with the result.
  -Remove   deletes the task. Nothing else.
  -DryRun   says what it would do, changes nothing.
It never starts, stops, arms or routes the bot and never touches NinjaTrader or an order.
Tests: tests\test_second_backup.py (LE_BB_T_LOG=<file>: the task is written to that file instead of Task Scheduler).
#>
param(
    [switch]$Remove,
    [switch]$DryRun,
    [string]$Python = ""
)

$ErrorActionPreference = 'Continue'
trap {
    Write-Host '  [FIX] The weekly backup task could not be set up: take a photo of this window and send it to Claude.' -ForegroundColor Red
    exit 1
}
$TaskName = 'OlympusWeeklyBackup'
$Root = Split-Path -Parent $PSScriptRoot
$Script = [System.IO.Path]::Combine([System.IO.Path]::Combine($Root, 'tools'), 'second_backup.py')

if ($Remove) {
    if ($DryRun) { Write-Host "  DRY RUN - would delete the task $TaskName"; exit 0 }
    if ($env:LE_BB_T_LOG) { Add-Content -LiteralPath $env:LE_BB_T_LOG -Value "TASK REMOVE $TaskName" }
    else { try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch { } }
    Write-Host "  [OK] weekly backup task $TaskName removed"
    exit 0
}

if (-not $Python) {
    if ($env:LE_PYTHON) { $Python = $env:LE_PYTHON }
    else {
        $cmd = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd) { $Python = $cmd.Source }
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) { Write-Host '  [FIX] python not found: the weekly backup task was not set up.'; exit 1 }
if (-not (Test-Path -LiteralPath $Script)) { Write-Host '  [FIX] tools\second_backup.py is missing: update the bot folder from the zip first.'; exit 1 }
$Pyw = [System.IO.Path]::Combine((Split-Path -Parent $Python), 'pythonw.exe')
if (-not (Test-Path -LiteralPath $Pyw)) { $Pyw = $Python }
$argLine = "-X utf8 `"$Script`" --weekly --quiet"

if ($DryRun) {
    Write-Host "  DRY RUN - would install the task $TaskName every Sunday 11:37 while you are signed in: $Pyw $argLine (start in $Root)"
    exit 0
}

if ($env:LE_BB_T_LOG) {
    Add-Content -LiteralPath $env:LE_BB_T_LOG -Value "TASK REGISTER $TaskName weekly Sunday 11:37: $Pyw $argLine"
    Write-Host "  [OK] weekly backup task ${TaskName}: every Sunday 11:37 (zip + mirror, then a phone push)"
    exit 0
}
try {
    $user = "$env:USERDOMAIN\$env:USERNAME"
    $action = New-ScheduledTaskAction -Execute $Pyw -Argument $argLine -WorkingDirectory $Root
    $weekly = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '11:37'
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $task = New-ScheduledTask -Action $action -Trigger @($weekly) -Settings $settings -Principal $principal `
        -Description "OLYMPUS: weekly code zip to the synced folder + git mirror push. Installed by tools\bat\BACKUP_SETUP.bat from $Root"
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
    Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
    Write-Host "  [OK] weekly backup task ${TaskName}: every Sunday 11:37 (zip + mirror, then a phone push)"
} catch {
    Write-Host "  [FIX] could not create the weekly backup task: $($_.Exception.Message)"
    Write-Host '        Send a photo of this window to Claude.'
    exit 1
}
exit 0
