<#
AGENCY MAIL task (EMAIL_SETUP.bat installs it, EMAIL_STOP.bat removes it; agency\autopilot\run.py).

  default   installs (or replaces) the Windows task "OlympusAgencyMail" (email + postcards): every 30 minutes while you are signed in it runs
            "python -m agency.autopilot run" with pythonw (no window), at most one at a time. The autopilot itself only sends
            Mon-Fri 9:00-16:00 ET, max 20 new businesses a day, and nothing at all unless EMAIL_SETUP.bat saved the phrase SEND EMAILS
            (else DRY RUN: your own test address only).
  -Remove   deletes the task. Nothing else.
  -DryRun   says what it would do, changes nothing.
It never starts, stops, arms or routes the trading bot and never touches NinjaTrader or an order.
Tests: tests\test_agency_autopilot.py (LE_BB_T_LOG=<file>: the task is written to that file instead of Task Scheduler).
#>
param(
    [switch]$Remove,
    [switch]$DryRun,
    [string]$Python = ""
)

$ErrorActionPreference = 'Continue'
trap {
    Write-Host '  [FIX] The email task could not be set up: take a photo of this window and send it to Claude.' -ForegroundColor Red
    exit 1
}
$TaskName = 'OlympusAgencyMail'
$Root = Split-Path -Parent $PSScriptRoot

if ($Remove) {
    if ($DryRun) { Write-Host "  DRY RUN - would delete the task $TaskName"; exit 0 }
    if ($env:LE_BB_T_LOG) { Add-Content -LiteralPath $env:LE_BB_T_LOG -Value "TASK REMOVE $TaskName" }
    else { try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch { } }
    Write-Host "  [OK] email task $TaskName removed"
    exit 0
}

if (-not $Python) {
    if ($env:LE_PYTHON) { $Python = $env:LE_PYTHON }
    else {
        $cmd = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd) { $Python = $cmd.Source }
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) { Write-Host '  [FIX] python not found: the email task was not set up.'; exit 1 }
$Pyw = [System.IO.Path]::Combine((Split-Path -Parent $Python), 'pythonw.exe')
if (-not (Test-Path -LiteralPath $Pyw)) { $Pyw = $Python }
$argLine = "-X utf8 -m agency.autopilot run"

if ($DryRun) {
    Write-Host "  DRY RUN - would install the task $TaskName every 30 minutes while you are signed in: $Pyw $argLine (start in $Root)"
    exit 0
}
if ($env:LE_BB_T_LOG) {
    Add-Content -LiteralPath $env:LE_BB_T_LOG -Value "TASK REGISTER $TaskName every 30 min: $Pyw $argLine"
    Write-Host "  [OK] email task ${TaskName}: every 30 minutes"
    exit 0
}
try {
    $user = "$env:USERDOMAIN\$env:USERNAME"
    $action = New-ScheduledTaskAction -Execute $Pyw -Argument $argLine -WorkingDirectory $Root
    $every = New-ScheduledTaskTrigger -Once -At '00:00' -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 1)
    $daily = New-ScheduledTaskTrigger -Daily -At '00:00'
    $daily.Repetition = $every.Repetition
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $task = New-ScheduledTask -Action $action -Trigger @($daily) -Settings $settings -Principal $principal `
        -Description "OLYMPUS: the Website Factory email autopilot (OFF until EMAIL_SETUP.bat + SEND EMAILS). Installed by EMAIL_SETUP.bat from $Root"
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
    Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
    Write-Host "  [OK] email task ${TaskName}: every 30 minutes (it only sends Mon-Fri 9-16 ET)"
} catch {
    Write-Host "  [FIX] could not create the email task: $($_.Exception.Message)"
    exit 1
}
exit 0
